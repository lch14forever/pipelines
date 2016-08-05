#!/usr/bin/env python3
from argparse import ArgumentParser
from collections import OrderedDict
from gzip import open
from os import path, remove
from re import findall
from sqlite3 import connect
from sys import argv

FIELDS = ['qname', 'hostname', 'owner', 'job_name', 'job_number', 'submission_time',
          'start_time', 'end_time', 'failed', 'exit_status', 'ru_wallclock', 'io', 'category', 'maxvmem',
          'h_rt', 'h_vmem', 'mem_free', 'openmp']

instance = ArgumentParser(description=__doc__)
instance.add_argument("-a", "--accounting", nargs="*", help="accounting file(s) in .gz")
instance.add_argument("-b", "--database", help="SQLite database filename")
instance.add_argument("-o", "--owner", nargs="*", help="job owner(s)")
#instance.add_argument("-v", "--view", nargs="*", help="SQL views(s)")
args = instance.parse_args()

if args.accounting and args.database:
	if (not path.isfile(args.database)):
		print ("CREATING DATABASE:\t" + args.database)
	else:
		remove (args.database)
		print ("REPLACING DATABASE:\t" + args.database)

	db = connect(args.database)
	db.execute('''CREATE TABLE accounting(
		qname			TEXT		NOT NULL,
		hostname		TEXT		NOT NULL,
		owner			TEXT		NOT NULL,
		job_name		TEXT		NOT NULL,
		job_number		INTEGER		NOT NULL,
		submission_time		INTEGER		NOT NULL,
		start_time		INTEGER		NOT NULL,
		end_time		INTEGER		NOT NULL,
		failed			INTEGER		NOT NULL,
		exit_status		INTEGER		NOT NULL,
		ru_wallclock		INTEGER		NOT NULL,
		io			INTEGER		NOT NULL,
		category		INTEGER		NOT NULL,
		maxvmem			INTEGER		NOT NULL,
		h_rt			INTEGER,
		h_vmem			INTEGER,
		mem_free		INTEGER,
		openmp			INTEGER
	);''')
	db.close()

	for acct in args.accounting:
		print (acct[-3:])
		with open(acct) as fh:
			for line in fh:
				l = line.decode().rstrip().split(':')
				if l[0].startswith('#'):
					continue
				
				owner_found = 0
				if args.owner:
					for owner in args.owner:
						if l[3] == owner:
							owner_found += 1
				if owner_found == 0:
					continue

				a = ''
				for f in FIELDS:
					a = (a + ", '" + f + "'")

				b = ''
				for j in [l[0], l[1], l[3], l[4], l[5], l[8], l[9], l[10], l[11], l[12], l[13], l[21], l[22], l[25]]:
					b = (b + ", '" + j + "'")

				c = ''
				if len(findall("h_rt=\d+", l[39])) > 0:
					c = (c + ", '" + findall("h_rt=\d+", l[39])[0][5:] + "'")
				else:
					c = (c + ", ''")

				if len(findall("h_vmem=\d+", l[39])) > 0:
					c = (c + ", '" + findall("h_vmem=\d+", l[39])[0][7:] + "'")
				else:
					c = (c + ", ''")

				if len(findall("mem_free=\d+", l[39])) > 0:
					c = (c + ", '" + findall("mem_free=\d+", l[39])[0][9:] + "'")
				else:
					c = (c + ", ''")

				if len(findall("OpenMP\s\d+", l[39])) > 0:
					c = (c + ", '" + findall("OpenMP\s\d+", l[39])[0].split(" ")[1] + "'")
				else:
					c = (c + ", ''")
#				print(c[2:])
				db = connect(args.database)
				db.execute("INSERT INTO accounting (" + a[2:] + ") VALUES (" + b[2:] + c + ");")
				db.commit()
				db.close()

else:
	print ("Please specify one or more accounting file(s) in .gz with -a or --accounting")
	print ("Please specify a SQLite database filename with -b or --database")
