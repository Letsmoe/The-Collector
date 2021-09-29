def getAttrFromSelection(selection, attr):
	if isinstance(selection, list):
		return [x[attr] for x in selection]
	else:
		return selection[attr]



def getMethodFromSelection(selection, attr):
	Operations = {
		"text": lambda x: x.text,
		"html": lambda x: str(x)
	}
	# ------------- Check if the selection is of type list or string ------------ #
	if isinstance(selection, list):
		return [Operations.get(attr)(x) for x in selection]
	else:
		# ------------------------ Check if selection is set ----------------------- #
		if selection is not None:
			return Operations.get(attr)(selection)


def checkDomain(Value, BaseUrl):
	# -------------------- Check if the given domain is valid ------------------- #
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

	def RunOperation(i, OpType, Op):
		return PreOps[OpType](Op.get("value"), i)

	for op in Operations:
		OpType = op.get("type")
		if isinstance(Value, list):
			Value = [RunOperation(i, OpType, op) for i in Value]
		elif isinstance(Value, str):
			Value = RunOperation(Value, OpType, op)
	return Value