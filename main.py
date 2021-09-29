import psycopg2
import WebScrape.config as cfg

class WebScraper:
	def __init__(self, configFile):
		self.configFile = configFile
		self.version = configFile.get('schema')
		self.config = self.parseConfig(configFile)
		self.conn = self.getConnection(configFile)
		self.calls = self.setupCalls(configFile)


class Connection(WebScraper):
	def getConnection(self, configFile):
		if self.version == "ContinuumWebScrape0.0.1V1" and configFile.get('writeSQL'):
			conn = psycopg2.connect(host=configFile.get('host'),
			port = configFile.get('port'),
			database=configFile.get('database'),
			user=configFile.get('user'),
			password=configFile.get('password'))
			return conn
