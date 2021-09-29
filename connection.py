import psycopg2

def getConnectionConfig(configFile):
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