#from selenium import webdriver
#from selenium.webdriver.common.keys import Keys
from concurrent.futures import ThreadPoolExecutor
import xxhash
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from seleniumrequests import Firefox
from selenium.webdriver.firefox.options import Options
import time
import pickle
import time
import re


import numpy as np
def getRanges(start, stop, step):
	return [(i + 1, i + step) for i in range(start, stop - ((stop - start) % step), step)]


options = Options()
options.headless = True

driver = Firefox(options = options, executable_path="./geckodriver.exe")
driver.get("https://members.onlytease.com/login")

username = driver.find_element_by_id("uid")
password = driver.find_element_by_id("pwd")

username.send_keys("moritztoll1@gmail.com")
password.send_keys("Geiloboy1")

driver.find_element_by_class_name("loginbtn.oas-rounded").click()
time.sleep(15)
cookies = driver.get_cookies()
driver.quit()
# ------------------------ Dump Cookies for later use ------------------------ #
pickle.dump(cookies, open("browser-cookies.pkl", "wb"))


cookies = pickle.load(open("browser-cookies.pkl", "rb"))
def initDriver(cookies):
	options = Options()
	options.headless = True
	driver = Firefox(options = options, executable_path = "./geckodriver.exe")
	driver.get("https://members.onlytease.com/")
	for cookie in cookies:
		driver.add_cookie(cookie)
	return driver


import os

ROOT_PATH = "./downloads"
START = 500
STOP = 1500
NUM = 5
scrapeRanges = getRanges(START, STOP, int((STOP - START) / NUM))

def imageDownload(resp, name):
	path = os.path.join(ROOT_PATH, name)
	if not os.path.isdir(path):
		os.makedirs(path)
	hashed = xxhash.xxh128_hexdigest(resp.content)
	FilePath = os.path.join(path, "%s.jpg" % hashed)
	if not os.path.isfile(FilePath):
		with open(FilePath, "wb") as f:
			f.write(resp.content)

def getImages(driver, url, name, start=1, end=1, fill = False):
	def makeUrl(i):
		if fill:
			return url % str(i).zfill(4 + len(str(i)) - len(str(i)))
		else:
			return url % str(i)

	with ThreadPoolExecutor(max_workers=25) as s:
		mapped = [makeUrl(i) for i in range(start, end)]
		futures = s.map(lambda x: driver.request("GET", x), mapped)
		for i in futures:
			imageDownload(i, name)


def startDriverScraping(r):
	driver = initDriver(cookies)
	print("Started Driver with Range -> " + str(r))
	for i in range(*r):
		print(i)
		driver.get("https://members.onlytease.com/gallery/ot/%s" % str(i))
		if driver.find_elements_by_class_name("jumbotron"):
			print("Aborted due to missing page.")
			continue

		InitialLink = WebDriverWait(driver, 10).until(lambda d: d.find_element_by_css_selector(".gallery-image img").get_attribute("data-srcset"))
		NumberLinks = WebDriverWait(driver, 10).until(lambda d: d.find_element_by_css_selector(".oas-pages .counter b:last-of-type").get_attribute("innerText"))
		ParsedLink = re.search("(https:\/\/.*?\/images\/thumbnails\/(.*?)\/.*?)_dpr2\.(jpg) 2x", InitialLink, re.IGNORECASE)
		Name = WebDriverWait(driver, 10).until(lambda d: d.find_element_by_css_selector(".model-name a").get_attribute("innerText"))

		ParsedLink = ParsedLink.groups()

		if ParsedLink[1] == "sets":
			start = int(re.search("\d+", os.path.split(ParsedLink[0])[1]).group(0))
			end = start + int(NumberLinks)
			url = os.path.split(ParsedLink[0])[0] + "/tnP%s_dpr3." + ParsedLink[2]
			getImages(driver, url, Name, start, end, False)
		elif ParsedLink[1] == "sets2":
			end = int(NumberLinks)
			url = os.path.split(ParsedLink[0])[0] + "/tnIMG_%s_dpr3." + ParsedLink[2]
			getImages(driver, url, Name, 1, end, True)
	print("Exited driver with range -> " + str(r))
	#driver.quit()

with ThreadPoolExecutor(max_workers=5) as t:
	t.map(startDriverScraping, scrapeRanges)

print("Done")