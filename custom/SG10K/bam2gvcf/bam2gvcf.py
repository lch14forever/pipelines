#!/usr/bin/env python3
"""{PIPELINE_NAME} pipeline (version: {PIPELINE_VERSION}): creates
pipeline-specific config files to given output directory and runs the
pipeline (unless otherwise requested).
"""
# generic usage {PIPELINE_NAME} and {PIPELINE_VERSION} replaced while
# printing usage

#--- standard library imports
#
import sys
import os
import argparse
import logging

#--- third-party imports
#
import yaml

#--- project specific imports
#
# add lib dir for this pipeline installation to PYTHONPATH
LIB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib"))
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)
from readunits import get_samples_and_readunits_from_cfgfile
from readunits import get_readunits_from_args
from pipelines import get_pipeline_version
from pipelines import PipelineHandler
from pipelines import get_site
from pipelines import logger as aux_logger
from pipelines import get_cluster_cfgfile

__author__ = "Andreas Wilm"
__email__ = "wilma@gis.a-star.edu.sg"
__copyright__ = "2016 Genome Institute of Singapore"
__license__ = "The MIT License (MIT)"


# only dump() and following do not automatically create aliases
yaml.Dumper.ignore_aliases = lambda *args: True


PIPELINE_BASEDIR = os.path.dirname(sys.argv[0])
CFG_DIR = os.path.join(PIPELINE_BASEDIR, "cfg")

# same as folder name. also used for cluster job names
PIPELINE_NAME = "SG10K"

DEFAULT_SLAVE_Q = {'GIS': None,
                   'NSCC': 'production'}
DEFAULT_MASTER_Q = {'GIS': None,
                    'NSCC': 'production'}

MARK_DUPS = True

# global logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '[{asctime}] {levelname:8s} {filename} {message}', style='{'))
logger.addHandler(handler)


def main():
    """main function
    """

    parser = argparse.ArgumentParser(description=__doc__.format(
        PIPELINE_NAME=PIPELINE_NAME, PIPELINE_VERSION=get_pipeline_version()))

    # generic args
    parser.add_argument('-o', "--outdir", required=True,
                        help="Output directory (must not exist)")
    parser.add_argument('--name',
                        help="Give this analysis run a name (used in email and report)")
    parser.add_argument('--no-mail', action='store_true',
                        help="Don't send mail on completion")
    site = get_site()
    default = DEFAULT_SLAVE_Q.get(site, None)
    parser.add_argument('-w', '--slave-q', default=default,
                        help="Queue to use for slave jobs (default: {})".format(default))
    default = DEFAULT_MASTER_Q.get(site, None)
    parser.add_argument('-m', '--master-q', default=default,
                        help="Queue to use for master job (default: {})".format(default))
    parser.add_argument('-n', '--no-run', action='store_true')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help="Increase verbosity")
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help="Decrease verbosity")
    cfg_group = parser.add_argument_group('Configuration files (advanced)')
    cfg_group.add_argument('--prev-cfg',
                           help="Previously used config. Also used to infer path to precalculated BAM files")
    for name, descr in [("references", "reference sequences"),
                        ("params", "parameters"),
                        ("modules", "modules")]:
        default = os.path.abspath(os.path.join(CFG_DIR, "{}.yaml".format(name)))
        cfg_group.add_argument('--{}-cfg'.format(name),
                               default=default,
                               help="Config-file (yaml) for {}. (default: {})".format(descr, default))

    # pipeline specific args
    #parser.add_argument('-1', "--fq1", nargs="+",
    #                    help="FastQ file/s (gzip only)."
    #                    " Multiple input files supported (auto-sorted)."
    #                    " Note: each file (or pair) gets a unique read-group id."
    #                    " Collides with --sample-cfg.")
    #parser.add_argument('-2', "--fq2", nargs="+",
    #                    help="FastQ file/s (if paired) (gzip only). See also --fq1")
    #parser.add_argument('-s', "--sample",
    #                    help="Sample name. Collides with --sample-cfg.")
    #parser.add_argument('-t', "--seqtype", required=True,
    #                    choices=['WGS', 'WES', 'targeted'],
    #                    help="Sequencing type")
    #parser.add_argument('-l', "--bed",
    #                    help="Bed file listing regions of interest."
    #                    " Required for WES and targeted sequencing.")

    args = parser.parse_args()

    # Repeateable -v and -q for setting logging level.
    # See https://www.reddit.com/r/Python/comments/3nctlm/what_python_tools_should_i_be_using_on_every/
    # and https://gist.github.com/andreas-wilm/b6031a84a33e652680d4
    # script -vv -> DEBUG
    # script -v -> INFO
    # script -> WARNING
    # script -q -> ERROR
    # script -qq -> CRITICAL
    # script -qqq -> no logging at all
    logger.setLevel(logging.WARN + 10*args.quiet - 10*args.verbose)
    aux_logger.setLevel(logging.WARN + 10*args.quiet - 10*args.verbose)

    if os.path.exists(args.outdir):
        logger.fatal("Output directory %s already exists", args.outdir)
        sys.exit(1)


    # samples is a dictionary with sample names as key (mostly just
    # one) and readunit keys as value. readunits is a dict with
    # readunits (think: fastq pairs with attributes) as value
    #if args.sample_cfg:
    #    if any([args.fq1, args.fq2, args.sample]):
    #        logger.fatal("Config file overrides fastq and sample input arguments."
    #                     " Use one or the other")
    #        sys.exit(1)
    #    if not os.path.exists(args.sample_cfg):
    #        logger.fatal("Config file %s does not exist", args.sample_cfg)
    #        sys.exit(1)
    #    samples, readunits = get_samples_and_readunits_from_cfgfile(args.sample_cfg)
    #else:
    #    if not all([args.fq1, args.sample]):
    #        logger.fatal("Need at least fq1 and sample without config file")
    #        sys.exit(1)
    #
    #    readunits = get_readunits_from_args(args.fq1, args.fq2)
    #    # all readunits go into this one sample specified on the command-line
    #    samples = dict()
    #    samples[args.sample] = list(readunits.keys())
    #
    #if args.seqtype in ['WES', 'targeted']:
    #    if not args.bed:
    #        logger.fatal("Analysis of exome and targeted sequence runs requires a bed file")
    #        sys.exit(1)
    #    else:
    #        if not os.path.exists(args.bed):
    #            logger.fatal("Bed file %s does not exist", args.sample_cfg)
    #            sys.exit(1)
    #        logger.warning("Compatilibity between bed file and"
    #                       " reference not checked")# FIXME

    with open(args.prev_cfg, 'r') as stream:
        try:
            prev_cfg = yaml.load(stream)
        except yaml.YAMLError as exc:
            logger.fatal("Error loading %s", REST_CFG)
            raise
    #import pdb; pdb.set_trace()
    #sys.stderr.write("TMP DEBUG {}\n".format(prev_cfg))
    
    # turn arguments into user_data that gets merged into pipeline config
    #
    # generic data first
    user_data = dict()
    user_data['mail_on_completion'] = not args.no_mail
    #user_data['readunits'] = prev_cfg['readunits'] 
    user_data['readunits'] = dict()# None won't work
    #user_data['samples'] = samples
    user_data['samples'] = prev_cfg['samples']
    if args.name:
        user_data['analysis_name'] = args.name
    #user_data['seqtype'] = args.seqtype
    user_data['seqtype'] = 'WGS'# SG10K
    #user_data['intervals'] = args.bed# always safe, might be used for WGS as well
    user_data['intervals'] = None#SG10K
    user_data['mark_dups'] = None# SG10K doesn't matter
    user_data['precalc_bam_dir'] = os.path.join(
        os.path.abspath(os.path.dirname(args.prev_cfg)), "out")

    pipeline_handler = PipelineHandler(
        PIPELINE_NAME, PIPELINE_BASEDIR,
        args.outdir, user_data, site=site,
        master_q=args.master_q,
        slave_q=args.slave_q,
        params_cfgfile=args.params_cfg,
        modules_cfgfile=args.modules_cfg,
        refs_cfgfile=args.references_cfg,
        cluster_cfgfile=get_cluster_cfgfile(CFG_DIR))
    pipeline_handler.setup_env()
    pipeline_handler.submit(args.no_run)


if __name__ == "__main__":
    main()
