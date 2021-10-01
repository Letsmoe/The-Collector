import json
import numpy as np
from requests_futures.sessions import FuturesSession
from bs4 import BeautifulSoup
import requests
import random
# --------------------------- Import local packages -------------------------- #
from connection import getConnectionConfig
from __selectionManipulation import *
from urllib.parse import urljoin


conn = getConnectionConfig(json.loads(open("F:/Projects/The Collector/config/bookstoreConfig.json").read())[0])

class ValueParser(object):
	def __init__(self, Obj, Selection, soup, UrlResponse, URLCarrier = False):
		Schema = Obj.get("name")
		self.soup = soup
		self.Operations = Obj.get("applyOperations")
		self.BaseUrl = UrlResponse.url
		self.Selection = Selection
		self.Value = self.getSelectionValue(Schema)
		if self.Operations:
			self.ApplyOperations()
		if URLCarrier is True:
			self.Value = self.CheckDomain()

	def CheckDomain(self):
		# -------------------- Check if the given domain is valid ------------------- #
		if isinstance(self.Value, str) and not self.Value.startswith(("http", "https", "//")):
			return urljoin(self.BaseUrl, self.Value)
		elif isinstance(self.Value, list):
			return [urljoin(self.BaseUrl, i) for i in self.Value]

	def ApplyOperations(self):
		# ----------------- Define operations that can be performed ----------------- #
		PreOps = {
			"String::groupRegExp": lambda val, i: ''.join(re.search(val, i).groups() if re.search(val, i) else []),
			"String::trimRight": lambda val, i: i.rstrip(val or None),
			"String::trimLeft": lambda val, i: i.lstrip(val or None),
			"String::trim": lambda val, i: i.strip(val or None),
			"String::->int": lambda val, i: int(i),
			"String::->bool": lambda val, i: bool(i),
			"String::->float": lambda val, i: float(i),
			"String::->list": lambda val, i: list(i)
		}

		for op in self.Operations:
			OpType = op.get("type")
			OperationValue = op.get("value")
			if isinstance(self.Value, list):
				self.Value = [PreOps[OpType](OperationValue, i) for i in self.Value]
			elif isinstance(self.Value, str):
				self.Value = PreOps[OpType](OperationValue, op)
		return self.Value

	def getSelectionValue(self, Schema):
		Parts = Schema.split("::")
		# If the reference is based on the object itself (?= _self)
		# All methods will be called on the reference
		# If it is based on the object of the parser, so the current page 
		# The value is being pulled from the current parsing object (response)
		# The reference will then equal "_page"
		Reference = Parts[0]
		Method = Parts[1]
		MethodAttribute = Parts[2]
		if Reference == "_self":
			# ----------------------- Call the specified method ----------------------- #
			if Method == "attribute":
				# ------------- Check if the selection is of type list or string ------------ #
				if isinstance(self.Selection, list):
					return [x[MethodAttribute] for x in self.Selection]
				else:
					return self.Selection[MethodAttribute]

			elif Method == "method":
				Operations = {
					"text": lambda x: x.text,
					"html": lambda x: str(x)
				}
				# ------------- Check if the selection is of type list or string ------------ #
				if self.Selection:
					if isinstance(self.Selection, list):
						return [Operations.get(MethodAttribute)(x) for x in self.Selection]
					else:
						return Operations.get(MethodAttribute)(self.Selection)

		elif Reference == "_page":
			print(self.soup)

class Collector(object):
	def __init__(self, path):
		self.path = path
		self.config = self.parseConfig(path)

	def scrapeWebsite(self, url : str, config : dict, rangeObject, topConfig : dict, carryOver : dict = {}, dieSilently=True, runAsync=False):
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
					Value = ValueParser(InsertionValue, Selection, soup, resp, URLCarrier = False).Value
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
						Value = ValueParser(Carry, Selection, soup, resp, URLCarrier = True).Value
						# ------------------ Call subroutine with new arguments ----------------- #
						if Carry.get("as") == "url":
							if instr.get("async") is True:
								self.scrapeWebsite("%s", config.get("subroutines").get(Subroutine), Value, topConfig, runAsync=True)
							else:
								self.scrapeWebsite("%s", config.get("subroutines").get(Subroutine), Value, topConfig, runAsync=False)

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


	def getRange(self, rangeObject):
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

	def parseConfig(self, path):
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
			Range = self.getRange(Instruction.get("range"))
			# ----------------------------- Start Scraping ----------------------------- #
			if Instruction.get("async") is True:
				self.scrapeWebsite(URL, Instruction, Range, Instruction, runAsync=True)
			else:
				self.scrapeWebsite(URL, Instruction, Range, Instruction, runAsync=False)



Collector("F:/Projects/The Collector/config/bookstoreConfig.json")