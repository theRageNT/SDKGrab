import re
import os
import sys
import collections
import datetime

pattern = "class\\s*([a-zA-Z_0-9]+)\\s*:\\s*public\\s*([a-zA-Z_0-9]+)[\\s\\r\\n]*[{][\\s\\r\\n]*public\\s*:(?:[\\s\\r\\n]*((?:[^\\r\\n]*//[^\\r\\n]*[\\s\\r\\n]*)+))?"
fieldPattern = "([^\\r\\n]*?)\\s*([a-zA-Z_0-9]+(?:\\s*[:]\\s*[0-9]+\\s*)?);\\s*//([^\\r\\n]*)"
structPattern = "struct\\s([A-Za-z0-9]*)\\n{\\n([\\t\\s*a-zA-Z_0-9;<>:/(),\[\]]+)};"
findFunc = "//\s\w*\s(\w*.\w*.\w*)\n//\s([\(\),\w\s]*)"
functionPattern = "//\sFunction\s(.*)\n//\s(.*)\n//\sParameters:\n([A-Za-z\/\s:\(\),_<>0-9*]+)\n\n"
functionPattern2 = "//\sFunction\s(.*)\n//\s(.*)\n(?://\sParameters:\n([A-Za-z\/\s:\(\),_<>0-9*]+)\n\n)?"
rpcPattern = "//\\s(\\w*\\s\\w*\**)\\s*(\\w*)"
structFiles = ["PUBG_Engine_structs.hpp", "PUBG_TslGame_structs.hpp"]
classFiles = ["PUBG_Engine_classes.hpp", "PUBG_TslGame_classes.hpp"]
funcFiles = ["PUBG_Engine_functions.cpp", "PUBG_TslGame_functions.cpp"]
xxx = ["FEncryptedObject","FRepMovement", "FVector", "FRotator", "FString", "FName", "FVector2D", "FUniqueNetIdRepl", "FVector_NetQuantizeNormal","FVector_NetQuantize100","FVector_NetQuantize10","FVector_NetQuantize"]


class NetField:
    def __init__(self, name, type1, transient):
        self.name = name
        self.type = type1
        self.transient = transient


class NetClass:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.fields = {}
        self.netfields = {}
        self.rpcs = {}


class NetFunction:
    def __init__(self, name, parent, type1):
        self.name = name
        self.type = type1
        self.parent = parent
        self.fields = {}

# we need to handle structs, so... detect if we are looking at the structs file, and use those regex? Then I guess add them to the netClass and NetField as per-normal.


def readClasses(folder, classes): #Process Classes
    print("Parsing Classes...")
    for file in classFiles:
        try:
            with open(os.path.join(folder,file), 'r') as f:
                data = f.read()
                result = re.findall(pattern, data)
                for clz in result:
                    name = clz[0]
                    parent = clz[1]
                    clazz = NetClass(name, parent)
                    classes[name] = clazz
                    fields = re.findall(fieldPattern, clz[2])
                    for field in fields:
                        type1 = field[0].replace("\t","")
                        if type1 == "struct FEncryptedObject":
                            type1 = "Object"
                        nme = field[1]
                        if " : " in nme:
                            type1 = "bool"
                            nme = nme.split(" : ")[0]
                        comments = field[2]
                        trans = False
                        if comments.find("Transient") != -1:
                            trans = True
                        clazz.fields[nme] = NetField(nme, type1, trans)
                        if comments.find("Net") != -1:
                            clazz.netfields[nme] = NetField(nme, type1, trans)
        except IOError as e:
            print("Cannot find .hpp file " + e.message)
            exit()


def readStructs(folder, classes): #Process Structs
    print("Parsing Structs...")
    for file in structFiles:
        try:
            with open(os.path.join(folder,file), 'r') as f:
                data = f.read()
                result = re.findall(structPattern, data)
                for clz in result:
                    name = clz[0] #name of struct
                    clazz = NetClass(name, "struct")
                    classes[name] = clazz
                    fields = re.findall(fieldPattern, clz[1])
                    for field in fields:
                        type1 = field[0].replace("\t", "")
                        if type1 == "struct FEncryptedObject":
                            type1 = "Object"
                        nme = field[1]
                        if " : " in nme:
                            type1 = "bool"
                            nme = nme.split(" : ")[0]
                        clazz.fields[nme] = NetField(nme, type1, False)
        except IOError as e:
            print("Cannot find .hpp file " + e.message)
            exit()


def readFunctions(folder, classes, funcs): #Process Functions
    print("Parsing Functions...")
    for file in funcFiles:
        try:
            with open(os.path.join(folder,file), 'r') as f:
                data = f.read()
                result = re.findall(functionPattern2, data)
                for function in result:
                    full = function[0]  # name of struct
                    cls = full.split(".")[1]  # parent (aka class, possibly without A or U
                    name = full.split(".")[2]  # actual name
                    comment = function[1] #the comment string (Net, Transient, etc)
                    if "Net" in comment: #This is networked, aka RPC.
                        f = NetFunction(name, cls, "RPC") #Create a "RPC" type Function Object
                        if function[2] is not None:
                            props = re.findall(rpcPattern, function[2])
                            for prop in props:
                                pType = prop[0]
                                pName = prop[1]
                                f.fields[pName] = NetField(pName, pType, False)
                        try:
                            classes[cls].rpcs[name] = f
                        except KeyError:
                            try:
                                cls1 = "A"+cls
                                classes[cls1].rpcs[name] = f
                            except KeyError:
                                cls2 = "U" + cls
                                classes[cls2].rpcs[name] = f

        except IOError as e:
            print("Cannot find .cpp file " + e.message)
            exit()
        except KeyError as e:
            wut = False
            if(e.message in classes): wut = True
            print("""
            I can't find {0} in classes:
            {1}
            """.format(e.message,wut))


def expandStruct(name, struct):
    cls = classes[struct]
    flds = {}
    for k in sorted(cls.fields.keys(), key=str.lower):
        f = cls.fields[k]
        nname = name+"_"+f.name
        flds[nname] = NetField(nname, f.type, f.transient)
    return flds

def clearFile(output, version):
    date = datetime.date.today()
    with open(output, 'w+') as f:
        f.writelines("""   _____  ____   __ __ ______ ______ _   __
  / ___/ / __ \ / //_// ____// ____// | / /
  \__ \ / / / // ,<  / / __ / __/  /  |/ / 
 ___/ // /_/ // /| |/ /_/ // /___ / /|  /  
/____//_____//_/ |_|\____//_____//_/ |_/ 
                BY RAGE
         Generated: {0}
         Game Version: {1}\n
""".format(date,version))

def writeLine(line, output):
    with open(output, 'a+') as f:
        f.writelines(line + "\n")

def displayProps(fileName, classes, output):
    print("Processing...")
    with open(fileName, 'r') as f:
        lines = f.readlines()
        for line in lines:
            c = 1 # Track how man normal fields we have.
            r = 0 # Track number of RPCs we have.
            cls = line.strip("\n")
            print("\nProcessing: " + line)
            print("\tHandles for: " + cls + ":")
            writeLine("\n\tHandles for: " + cls + ":", output)
            harchy = collections.deque()
            while (True):
                try:
                    harchy.appendleft(cls)
                    cls = classes[cls].parent
                except KeyError, e:
                    pass
                    break
            i = 0 # Track how far we are into our Hiearchy and display appropriately
            for _cls in harchy:
                try:
                    lne = "\t"*i + "\t\t-->\n" + "\t"*i + "\t\t" + _cls
                    print(lne)
                    writeLine(lne, output)
                    clash = classes[_cls]
                    total = dict(clash.netfields, **clash.rpcs)
                    for k in sorted(total, key=str.lower):
                        f = total[k]
                        ## First let's check if it's an RPC, and perform out first split there:
                        if(f.type != "RPC"): ## If it's not an RPC, handle as per standard.
                            if " " in f.type: #If there is a space in the type, which means we can split it and figure out if it's a struct.
                                if (f.type.split(" ")[0] == "struct" and f.type.split(" ")[1] not in xxx): ## If it is a struct that is not in our ignore list. This will expand structs and handle that.
                                    tpe = f.type.split(" ")[1]
                                    nfields = expandStruct(f.name, tpe)
                                    for k in sorted(nfields, key=str.lower):
                                        nf = nfields[k]
                                        lne = "\t" * i + "\t\t\t({2}) :: Name: {0} | Type: {1}".format(nf.name, nf.type, c)
                                        writeLine(lne, output)
                                        print(lne)
                                        c += 1
                                else: ## There is a space but it is in our ignore list.
                                    if f.transient:
                                        lne = "\t" * i + "\t\t\t({2}) :: Name: {0} | Type: {1} <Transient>".format(f.name, f.type, c)
                                        writeLine(lne, output)
                                        print(lne)
                                    else:
                                        lne = "\t" * i + "\t\t\t({2}) :: Name: {0} | Type: {1}".format(f.name, f.type, c)
                                        writeLine(lne, output)
                                        print(lne)
                                    c += 1
                            else: ## No Space in the name
                                if f.transient:
                                    lne = "\t" * i + "\t\t\t({2}) :: Name: {0} | Type: {1} <Transient>".format(f.name, f.type, c)
                                    writeLine(lne, output)
                                    print(lne)
                                else:
                                    lne = "\t" * i + "\t\t\t({2}) :: Name: {0} | Type: {1}".format(f.name, f.type, c)
                                    writeLine(lne, output)
                                    print(lne)
                                c += 1
                        else:
                            cls = f.parent
                            name = f.name
                            lne = "\t" * i + "\t\t\t[{1}] :: Name: {0} **RPC**".format(name, r)
                            writeLine(lne, output)
                            print(lne)
                            for j in sorted(f.fields, key=str.lower):
                                prop = f.fields[j]
                                lne = "\t" * i + "\t\t\t\t| Name: {0} | Type: {1}".format(prop.name, prop.type, r)
                                writeLine(lne, output)
                                print(lne)
                        r += 1 #increase R but not C, this is an RPC so it does not affect normal Props.
                    i += 1
                except KeyError, e:
                    if (e.message != "UObject"):
                        print(sys.exc_info())
                    else:
                        i += 1
                        pass
                except IOError, e:
                    print('File IO Issue... investigate please!')
                    exit()

if __name__ == "__main__":
    #Parse Command Line
    # USAGE: sdkgrab.py (LOCATION TO .hpp FILES [default current dir]) (LOCATION OF classes.txt [default current dir]) (save file name [default output.txt])
    curdir = os.path.dirname(os.path.abspath(__file__))
    if(len(sys.argv) == 1):
        folder = curdir
        fileName = os.path.join(curdir, "classes.txt")
        output = os.path.join(curdir, "output.txt")
    elif(len(sys.argv) == 2):
        folder = os.path.join(sys.argv[1])
        fileName = os.path.join(curdir, "classes.txt")
        output = os.path.join(curdir, "output.txt")
    elif (len(sys.argv) == 3):
        folder = os.path.join(sys.argv[1])
        fileName = os.path.join(sys.argv[2], "classes.txt")
        output = os.path.join(curdir, "output.txt")
    elif (len(sys.argv) == 4):
        folder = os.path.join(sys.argv[1])
        fileName = os.path.join(sys.argv[2], "classes.txt")
        output = os.path.join(curdir, sys.argv[3])
    else:
        print("USAGE: sdkGrab.py (LOCATION TO .hpp FILES [default current dir]) (LOCATION OF classes.txt [default current dir]) (save file name [default output.txt])")
        exit()
    version = raw_input("Please enter game version this SDK is for: ")
    classes = {}
    funcs = {}
    clearFile(output, version)
    readClasses(folder, classes)
    readStructs(folder, classes)
    readFunctions(folder, classes, funcs)
    displayProps(fileName, classes, output)
    print("***************Complete!***************")


