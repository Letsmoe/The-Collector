import json
import re
import os
import numpy as np
from requests_futures.sessions import FuturesSession
from bs4 import BeautifulSoup
import psycopg2
import requests
import random


def getConnection(configFile):
	#self.version == "ContinuumWebScrape0.0.1V1" and 
	SQLInformation = configFile.get('sql')
	if configFile.get('writeSQL'):
		conn = psycopg2.connect(host=SQLInformation.get('host'),
		port = SQLInformation.get('port'),
		database=SQLInformation.get('database'),
		user=SQLInformation.get('user'),
		password=SQLInformation.get('password'))
		return conn
	else:
		raise Exception("Couldn't connect to database, the config doesn't contain connection information")
conn = getConnection(json.loads(open("F:/Projects/Scape Cluster/config/config.json").read())[0])


def getAttrFromSelection(selection, attr):
	if isinstance(selection, list):
		return [x[attr] for x in selection]
	else:
		return selection[attr]

def getMethodFromSelection(selection, attr):
	if isinstance(selection, list):
		if attr == "text":
			return [x.text for x in selection]
		elif attr == "html":
			return [str(x) for x in selection]
	else:
		# ------------------------ Check if selection is set ----------------------- #
		if selection is not None:
			if attr == "text":
				return selection.text
			elif attr == "html":
				return str(selection)


def checkDomain(Value, BaseUrl):
	if isinstance(Value, str) and not Value.startswith(("http", "https", "//")):
		Value = "http://" + Value
		return Value
	elif isinstance(Value, list):
		NewValue = []
		for i in Value:
			if i.startswith(("../", "./")):
				NewValue.append(os.path.join(BaseUrl, i))
			elif i.startswith("/") or not i.startswith(("http://", "https://", "//", "/")):
				NewValue.append(os.path.join(os.path.split(BaseUrl)[0], i).replace("\\","/"))
		return NewValue

def ApplyOperations(Value, Operations):
	PreOps = {
		"String::groupRegExp": lambda val, i: ''.join(re.search(val, i).groups() if re.search(val, i) else []),
		"String::trimRight": lambda val, i: i.rstrip(val or None),
		"String::trimLeft": lambda val, i: i.lstrip(val or None),
		"String::trim": lambda val, i: i.strip(val or None),
	}

	def RunOperation(i, OpType, Op):
		return PreOps[OpType](Op.get("value"), i)
				

	for op in Operations:
		OpType = op.get("type")
		if isinstance(Value, list):
			NewList = []
			for i in Value:
				NewList.append(RunOperation(i, OpType, op))
			Value = NewList
		elif isinstance(Value, str):
			Value = RunOperation(Value, OpType, op)
	return Value
	
def scrapeWebsite(url : str, config : dict, rangeObject, topConfig : dict, carryOver : dict = {}, dieSilently=True, runAsync=False):
	def PageReceivedCallback(resp, *args, **kwargs):
		if resp.status_code != 200 and dieSilently is False:
			raise Exception("The server did not answer with status code 200, the request was answered like this instead: " + str(resp.status_code))
		elif dieSilently is True and resp.status_code != 200:
			return
		# --------------- Convert the response to a traversable soup --------------- #
		soup = BeautifulSoup(resp.content, "html5lib")
		# ----------------- Define an object to capture all results ---------------- #
		ResultObject = {}
		# ----------- Loop through all instructions in the passed config ----------- #
		ParsingSchema = config.get("parsingSchema")
		for instr in ParsingSchema:
			Name = instr.get("name")
			Selector = instr.get("cssSelector")
			DontInsert = instr.get("dontInsert")
			# ---------------- Check if config says to only select one ---------------- #
			if instr.get("selectOne") is True:
				Selection = soup.select_one(Selector)
			else:
				Selection = soup.select(Selector)
			# --------------------- Check to insert into database --------------------- #
			if DontInsert is False:
				insertWith = instr.get("insertWith").copy()
				# ------------------------- Get Value from object ------------------------ #
				InsertionValue = insertWith.get("value")
				NameSplit = InsertionValue.get("name").split("::")
				# ----------------------- Filter by first parameter ---------------------- #
				if NameSplit[0] == "attribute":
					Value = getAttrFromSelection(Selection, NameSplit[1])
				elif NameSplit[0] == "method":
					Value = getMethodFromSelection(Selection, NameSplit[1])
				# --------------------- Apply Operations if present -------------------- #
				Operations = insertWith.get("applyOperations")
				if Operations:
					Value = ApplyOperations(Value, Operations)
				insertWith["value"] = Value
				ResultObject[Name] = insertWith
			else:
				ResultObject[Name] = {"value": Selection, "insertCombine": False, "dontInsert": True}
			# ----------- Check if a subroutine is called with any arguments ----------- #
			Subroutine =  instr.get("startCall")
			if isinstance(Subroutine, str):
				CarryOver = instr.get("carryOver")
				for Carry in CarryOver:
					NameSplit = Carry.get("name").split("::")
					if NameSplit[0] == "attribute":
						Value = getAttrFromSelection(Selection, NameSplit[1])
						# --------------------- Apply Operations if present -------------------- #
						Operations = Carry.get("applyOperations")
						if Operations:
							Value = ApplyOperations(Value, Operations)

						if NameSplit[1] in ["href", "src", "rel"]:
							Value = checkDomain(Value, resp.url)
					else:
						print(NameSplit)
					# ------------------ Call subroutine with new arguments ----------------- #
					if Carry.get("as") == "url":
						if instr.get("async") is True:
							scrapeWebsite("%s", config.get("subroutines").get(Subroutine), Value, topConfig, runAsync=True)
						else:
							scrapeWebsite("%s", config.get("subroutines").get(Subroutine), Value, topConfig, runAsync=False)

		# ---------------- Open a cursor to prepare for insertion ---------------- #
		if topConfig.get("writeSQL") is True:
			Insertions = {}
			# ----------------------- Prepare insertions object ----------------------- #
			for i in ResultObject:
				Result = ResultObject[i]
				# --- Continue if the element shall not be inserted into the database. --- #
				if Result.get("dontInsert") is True:
					continue

				combine = Result.get("insertCombine")
				if combine:
					if Insertions.get(combine) is not None:
						Insertions[combine].append(Result)
					else:
						Insertions[combine] = [Result]
				else:
					chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
					Insertions[''.join(random.choice(chars) for _ in range(16))] = Result

			for i in Insertions:
				ValueObject = Insertions[i]
				Columns = ','.join(list(dict.fromkeys([x["column"] for x in ValueObject])))
				Values = [x["value"] for x in ValueObject]

				ValuePlaceholder = ','.join(["%s" for x in range(len(Values))])
				with conn.cursor() as cursor:
					cursor.execute(("INSERT INTO " + ValueObject[0].get("table") + " (" + Columns + ") VALUES (" + ValuePlaceholder + ")"), tuple(Values))
					conn.commit()
					cursor.close()
					
	if runAsync is True:
		with FuturesSession(max_workers=25) as sess:
			obj = [sess.get(url % i, hooks={
			'response': PageReceivedCallback,
		}) for i in rangeObject]
			for req in obj:
				req.result()
	else:
		for i in rangeObject:
			req = requests.get(url % i)
			PageReceivedCallback(req)


def getRange(rangeObject):
	RangeValue = rangeObject.get("value")
	if isinstance(RangeValue, str):
		RangeValue = list(RangeValue)
	elif isinstance(RangeValue, int):
		RangeValue = np.arange(rangeObject.get("start"), RangeValue, rangeObject.get("stepSize"))
	elif isinstance(RangeValue, list):
		RangeValue = RangeValue
	else:
		raise ValueError("Range is not any of type [str, int, list]")
	return RangeValue


def parseConfig(path):
	VALID_FORMATS = [".json", ".xml", ".yml"]
	extension = os.path.splitext(path)[1]
	# ------------------------------- Check Format ------------------------------ #
	if extension not in VALID_FORMATS:
		raise TypeError("The given file is of type \"" + extension + "\" which is not supported.")
	else:
		file = open(path)
		configFile = json.loads(file.read())
	# ---------------------- Loop Through all instructions ---------------------- #
	for Instruction in configFile:
		URL = Instruction.get("baseUrl")
		# --------------------------- Setup range object --------------------------- #
		Range = getRange(Instruction.get("range"))
		
		# ----------------------------- Start Scraping ----------------------------- #
		if Instruction.get("async") is True:
			scrapeWebsite(URL, Instruction, Range, Instruction, runAsync=True)
		else:
			scrapeWebsite(URL, Instruction, Range, Instruction, runAsync=False)


parseConfig("F:/Projects/Scape Cluster/config/config.json")