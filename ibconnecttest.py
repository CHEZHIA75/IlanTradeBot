from ib_insync import *

ib = IB()
ib.connect('127.0.0.1', 4002, clientId=321)  # use 7497 if live
print("✅ Connected to IB Gateway")