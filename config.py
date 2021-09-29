import os
import json
from main import *

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