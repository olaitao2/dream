# ===========================================================================
# Copyright 2013 Georgios Dagkakis
#
# This file is part of DREAM.
#
# DREAM is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# DREAM is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with DREAM.  If not, see <http://www.gnu.org/licenses/>.
# ===========================================================================
'''
Created on 7 May 2013

@author: George
'''
'''
main script. Reads data from JSON, generates and runs the simulation and prints the results to excel
'''

from SimPy.Simulation import *
from Source import Source
from Globals import G
from Machine import Machine
from Exit import Exit
from Queue import Queue
from QueueLIFO import QueueLIFO
from Repairman import Repairman
from Part import Part
from Frame import Frame
from Assembly import Assembly
from Dismantle import Dismantle
from Conveyer import Conveyer
import xlwt
import xlrd
import time
import numpy as np
import json
from random import Random
import sys
import os.path

#reads general simulation inputs
def readGeneralInput():
    general=G.JSONData['general']
    G.numberOfReplications=int(general.get('numberOfReplications', '1'))
    G.maxSimTime=float(general.get('maxSimTime', '100'))
    G.trace=general.get('trace', 'No')
    G.confidenceLevel=float(general.get('confidenceLevel', '0.95'))

#creates the simulation objects
def createObjects():
    #Read the json data
    coreObjectList = G.JSONData['coreObject']
    modelResourceList = G.JSONData['modelResource']
   
    #define the lists
    G.SourceList=[]
    G.MachineList=[]
    G.ExitList=[]
    G.QueueList=[]    
    G.RepairmanList=[]
    G.AssemblyList=[]
    G.DismantleList=[]
    G.ConveyerList=[]
    
    #loop through all the model resources 
    #read the data and create them
    for model_resource in modelResourceList:
        resourceClass = model_resource.get('_class', 'not found')
        if resourceClass=='Dream.Repairman':
            id = model_resource.get('id', 'not found')
            name = model_resource.get('name', 'not found')
            capacity = int(model_resource.get('capacity', '1'))
            R = Repairman(id, name, capacity)
            G.RepairmanList.append(R)                   
    
    #loop through all the core objects    
    #read the data and create them
    for core_object in coreObjectList:
        objClass=core_object.get('_class', 'not found')   
        if objClass=='Dream.Source':
            id=core_object.get('id', 'not found')
            name=core_object.get('name', 'not found')
            interarrivalTime=core_object.get('interarrivalTime', 'not found')
            distributionType=interarrivalTime.get('distributionType', 'not found')
            mean=float(interarrivalTime.get('mean', '0'))        
            entity=str_to_class(core_object.get('entity', 'not found'))
            successorList=core_object.get('successorList', 'not found')
            S=Source(id, name, distributionType, mean, entity)
            S.nextIds=successorList
            G.SourceList.append(S)
            G.ObjList.append(S)
            
        elif objClass=='Dream.Machine':
            id=core_object.get('id', 'not found')
            name=core_object.get('name', 'not found')
            processingTime=core_object.get('processingTime', 'not found')
            distributionType=processingTime.get('distributionType', 'not found')
            mean=float(processingTime.get('mean', '0'))  
            stdev=float(processingTime.get('stdev', '0'))  
            min=float(processingTime.get('min', '0')) 
            max=float(processingTime.get('max', '0'))
            failures=core_object.get('failures', 'not found')  
            failureDistribution=failures.get('failureDistribution', 'not found')
            MTTF=float(failures.get('MTTF', '0'))   
            MTTR=float(failures.get('MTTR', '0')) 
            availability=float(failures.get('availability', '0'))  
            needRepairman=failures.get('repairman', 'None')
            if(needRepairman=='None'):
                repairman=needRepairman
            else: 
                for j in range(len(G.RepairmanList)):
                    if(G.RepairmanList[j].id==needRepairman):
                        repairman=G.RepairmanList[j]
            successorList=core_object.get('successorList', 'not found')
            M=Machine(id, name, 1, distributionType, [mean,stdev,min,max], failureDistribution,
                                                    MTTF, MTTR, availability, repairman)
            M.nextIds=successorList
            G.MachineList.append(M)
            G.ObjList.append(M)
            
        elif objClass=='Dream.Exit':
            id=core_object.get('id', 'not found')
            name=core_object.get('name', 'not found')
            E=Exit(id, name)
            G.ExitList.append(E)
            G.ObjList.append(E)
            
        elif objClass=='Dream.Queue':
            id=core_object.get('id', 'not found')
            name=core_object.get('name', 'not found')
            successorList=core_object.get('successorList', 'not found')
            capacity=int(core_object.get('capacity', '1'))
            isDummy=bool(int(core_object.get('isDummy', '0')))
            Q=Queue(id, name, capacity, isDummy)
            Q.nextIds=successorList
            G.QueueList.append(Q)
            G.ObjList.append(Q)
            
        elif objClass=='Dream.Assembly':
            id=core_object.get('id', 'not found')
            name=core_object.get('name', 'not found')
            processingTime=core_object.get('processingTime', 'not found')
            distributionType=processingTime.get('distributionType', 'not found')
            mean=float(processingTime.get('mean', '0'))  
            stdev=float(processingTime.get('stdev', '0'))  
            min=float(processingTime.get('min', '0')) 
            max=float(processingTime.get('max', '0'))
            #predecessorPartList=core_object.get('predecessorPartList', 'not found')
            #predecessorFrameList=core_object.get('predecessorFrameList', 'not found')
            successorList=core_object.get('successorList', 'not found')
            A=Assembly(id, name, distributionType, [mean,stdev,min,max])
            #A.previousPartIds=predecessorPartList
            #A.previousFrameIds=predecessorFrameList
            A.nextIds=successorList
            G.AssemblyList.append(A)
            G.ObjList.append(A)
            
        elif objClass=='Dream.Dismantle':
            id=core_object.get('id', 'not found')
            name=core_object.get('name', 'not found')
            processingTime=core_object.get('processingTime', 'not found')
            distributionType=processingTime.get('distributionType', 'not found')
            mean=float(processingTime.get('mean', '0'))  
            stdev=float(processingTime.get('stdev', '0'))  
            min=float(processingTime.get('min', '0')) 
            max=float(processingTime.get('max', '0'))
            successorList=core_object.get('successorList', 'not found')
            successorPartList=core_object.get('successorPartList', 'not found')
            successorFrameList=core_object.get('successorFrameList', 'not found')
            D=Dismantle(id, name, distributionType, [mean,stdev,min,max])
            D.nextPartIds=successorPartList
            D.nextFrameIds=successorFrameList
            D.nextIds=successorList
            G.DismantleList.append(D)
            G.ObjList.append(D)
            
        elif objClass=='Dream.Conveyer':
            id=core_object.get('id', 'not found')
            name=core_object.get('name', 'not found')
            length=float(core_object.get('length', '10'))
            speed=float(core_object.get('speed', '1'))
            successorList=core_object.get('successorList', 'not found')
            C=Conveyer(id, name, length, speed)
            C.nextIds=successorList
            G.ObjList.append(C)
            G.ConveyerList.append(C)
            
    #loop through all the core objects    
    #to read predecessors
    for core_object in G.ObjList:
        #loop through all the nextIds of the object
        for nextId in core_object.nextIds:
            #loop through all the core objects to find the on that has the id that was read in the successorList
            for possible_successor in G.ObjList:
                if possible_successor.id==nextId:
                    possible_successor.previousIds.append(core_object.id)            

#defines the topology (predecessors and successors for all the objects)
def setTopology():
    #loop through all the objects  
    for core_object in G.ObjList:
        next=[]
        previous=[]
        for j in range(len(core_object.previousIds)):
            for q in range(len(G.ObjList)):
                if G.ObjList[q].id==core_object.previousIds[j]:
                    previous.append(G.ObjList[q])
                    
        for j in range(len(core_object.nextIds)):
            for q in range(len(G.ObjList)):
                if G.ObjList[q].id==core_object.nextIds[j]:
                    next.append(G.ObjList[q])      
                    
                    
        if core_object.type=="Source":
            core_object.defineRouting(next)
        elif core_object.type=="Exit":
            core_object.defineRouting(previous)
        #Dismantle should be changed to identify what the the successor is.
        #nextPart and nextFrame will become problematic    
        elif core_object.type=="Dismantle":
            nextPart=[]
            nextFrame=[]
            for j in range(len(core_object.nextPartIds)):
                for q in range(len(G.ObjList)):
                    if G.ObjList[q].id==core_object.nextPartIds[j]:
                        nextPart.append(G.ObjList[q])
            for j in range(len(core_object.nextFrameIds)):
                for q in range(len(G.ObjList)):
                    if G.ObjList[q].id==core_object.nextFrameIds[j]:
                        nextFrame.append(G.ObjList[q])
            core_object.defineRouting(previous, nextPart, nextFrame)
        else:
            core_object.defineRouting(previous, next)

#used to convert a string read from the input to object type
def str_to_class(str):
    return getattr(sys.modules[__name__], str)

#initializes all the objects that are in the topology
def initializeObjects():
    for core_object in G.ObjList:
        core_object.initialize()
    for repairman in G.RepairmanList:
        repairman.initialize()

#activates all the objects    
def activateObjects():
    for core_object in G.ObjList:
        try:
            activate(core_object, core_object.run())
        except AttributeError:
            pass

#the main script that is ran
def main(argv=[], input_data=None):
    argv = argv or sys.argv[1:]

    #create an empty list to store all the objects in   
    G.ObjList=[]

    if input_data is None:
      # user passes the topology filename as first argument to the program
      filename = argv[0]
      try:
          G.JSONFile=open(filename, "r")
      except IOError:
          print "%s could not be open" % filename
          return "ERROR"
      G.InputData=G.JSONFile.read()
    else:
      G.InputData = input_data

    start=time.time()   #start counting execution time 

    #read the input from the JSON file and create the line
    G.JSONData=json.loads(G.InputData)
    readGeneralInput()
    createObjects()
    setTopology() 

    
    #run the experiment (replications)          
    for i in xrange(G.numberOfReplications):
        print "start run number "+str(i+1) 
        G.seed+=1
        G.Rnd=Random(G.seed) 
              
        initialize()                        #initialize the simulation 
        initializeObjects()
        activateObjects()
                            
        simulate(until=G.maxSimTime)      #start the simulation
        
        #carry on the post processing operations for every object in the topology       
        for core_object in G.ObjList:
            core_object.postProcessing(G.maxSimTime)
            
        #carry on the post processing operations for every model resource in the topology       
        for model_resource in G.RepairmanList:
            model_resource.postProcessing(G.maxSimTime)
            
        '''    
        #output trace to excel
        if(G.trace=="Yes"):
            G.traceFile.save('trace'+str(i+1)+'.xls')
            G.traceIndex=0    #index that shows in what row we are
            G.sheetIndex=1    #index that shows in what sheet we are
            G.traceFile = xlwt.Workbook()     #create excel file
            G.traceSheet = G.traceFile.add_sheet('sheet '+str(G.sheetIndex), cell_overwrite_ok=True)  #create excel sheet
        
    G.outputSheet.write(G.outputIndex,0, "Execution Time")
    G.outputSheet.write(G.outputIndex,1, str(time.time()-start)+" seconds")
    G.outputIndex+=2 
    '''
    
    G.outputJSONFile=open('outputJSON.json', mode='w')
    G.outputJSON['_class'] = 'Dream.Simulation';
    G.outputJSON['general'] ={};
    G.outputJSON['general']['_class'] = 'Dream.Configuration';
    G.outputJSON['general']['totalExecutionTime'] = (time.time()-start);
    G.outputJSON['modelResource'] =[];
    G.outputJSON['coreObject'] =[];
    
    #output data to JSON for every object in the topology         
    for core_object in G.ObjList:
        try:
            core_object.outputResultsJSON()
        except AttributeError:
            pass
        
    #output data to JSON for every resource in the topology         
    for model_resource in G.RepairmanList:
        try:
            model_resource.outputResultsJSON()
        except AttributeError:
            pass
         
    outputJSONString=json.dumps(G.outputJSON, indent=True)
    G.outputJSONFile.write(outputJSONString)
       
    '''    
    #output data to excel for every object in the topology         
    for core_object in G.ObjList:
        core_object.outputResultsXL(G.maxSimTime)
        
    #output data to excel for every resource in the topology         
    for model_resource in G.RepairmanList:
        model_resource.outputResultsXL(G.maxSimTime)
      
    G.outputFile.save("output.xls")      
    '''
    
    print "execution time="+str(time.time()-start)  
    if input_data:
      return outputJSONString
        
if __name__ == '__main__':
    main()

