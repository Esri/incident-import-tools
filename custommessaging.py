import arcpy
class MsgType:
    INF = "INFORMATIVE"
    WRN = "WARNING"
    ERR = "ERROR"

class Message:
    def __init__(self, msgID, msg, msgType):
        self.msgID = msgID
        self.msg = msg
        self.msgType = msgType

## Common Functions
def printMessage(msgObj, messageVar1=None, messageVar2=None):
    try: #Try printing message from message xml first
        arcpy.AddIDMessage(msgObj.msgType, msgObj.msgID, messageVar1, messageVar2)
    except:
        message = msgObj.msg.format(messageVar1, messageVar2)
        if msgObj.msgType == MsgType.INF:
            arcpy.AddMessage(message)
        elif msgObj.msgType == MsgType.WRN:
            arcpy.AddWarning(message)
        elif msgObj.msgType == MsgType.ERR:
            arcpy.AddError(message)
    return

def validationMessage(msgObj,paramObj, messageVar1=None, messageVar2=None):
    try:
        paramObj.setIDMessage(msgObj.msgType,msgObj.msgID,messageVar1, messageVar2)
    except:
        message = msgObj.msg.format(messageVar1, messageVar2)
        if msgObj.msgType == MsgType.WRN:
            paramObj.setWarningMessage(message)
        elif msgObj.msgType == MsgType.ERR:
            paramObj.setErrorMessage(message)
    return

def retrieveMessage(msgObj, messageVar1=None, messageVar2=None):
    try:
        message = arcpy.GetIDMessage(msgObj.msgID)
        if not message:
            raise Exception
        message = message.replace("%1","{0}")
        message = message.replace("%2","{1}")
    except:
        message = msgObj.msg
    message = msgObj.msg.format(messageVar1, messageVar2)
    return message