import json
import numpy as np
from requests_futures.sessions import FuturesSession
from bs4 import BeautifulSoup
import requests
import random
# --------------------------- Import local packages -------------------------- #
from connection import getConnectionConfig
from __selectionManipulation import *
from config import parseConfig

conn = getConnectionConfig(json.loads(open("F:/Projects/The Collector/config/config.json").read())[0])

def parseValue(inp, Selection, Operations):
	# ------------- Split the input at each :: to filter parameters ------------- #
	NameSplit = inp.split('::')
	if NameSplit[0] == "attribute":
		Value = getAttrFromSelection(Selection, NameSplit[1])
	elif NameSplit[0] == "method":
		Value = getMethodFromSelection(Selection, NameSplit[1])
	else:
		Value = Selection

	if Operations:
		Value = ApplyOperations(Value, Operations)
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
				# ------- Filter by first parameter and apply Operations if present ------ #
				Operations = insertWith.get("applyOperations")
				Value = parseValue(InsertionValue.get("name"), Selection, Operations)
				insertWith["value"] = Value
				ResultObject[Name] = insertWith
			else:
				ResultObject[Name] = {"value": Selection, "insertCombine": False, "dontInsert": True}

			# -------- Check if the url of the object should be saved to a file ------- #
			SaveToFile = instr.get("saveToFile")
			if SaveToFile:
				URL = SaveToFile.get("url")
				print(SaveToFile)
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


parseConfig("F:/Projects/The Collector/config/config.json")