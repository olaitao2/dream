# ===========================================================================
# Copyright 2013 University of Limerick
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
Created on 22 Nov 2012

@author: Ioannis
'''

'''
models an operator that operates a machine
'''

# from SimPy.Simulation import Resource, now
import simpy
import xlwt
from ObjectResource import ObjectResource

# ===========================================================================
#                 the resource that operates the machines
# ===========================================================================
class Operator(ObjectResource):
    family='Operator'  
    
    def __init__(self, id, name, capacity=1, schedulingRule='FIFO'):
        ObjectResource.__init__(self)
        self.id=id
        self.objName=name
        self.capacity=capacity      # repairman is an instance of resource
        self.type="Operator"
        # lists to hold statistics of multiple runs
        self.Waiting=[]             # holds the percentage of waiting time 
        self.Working=[]             # holds the percentage of working time 
    
        # the following attributes are not used by the Repairman
        self.schedulingRule=schedulingRule      #the scheduling rule that the Queue follows
        self.multipleCriterionList=[]           #list with the criteria used to sort the Entities in the Queue
        SRlist = [schedulingRule]
        if schedulingRule.startswith("MC"):     # if the first criterion is MC aka multiple criteria
            SRlist = schedulingRule.split("-")  # split the string of the criteria (delimiter -)
            self.schedulingRule=SRlist.pop(0)   # take the first criterion of the list
            self.multipleCriterionList=SRlist   # hold the criteria list in the property multipleCriterionList
            
        for scheduling_rule in SRlist:
          if scheduling_rule not in self.getSupportedSchedulingRules():
            raise ValueError("Unknown scheduling rule %s for %s" %
              (scheduling_rule, id))
        
        # the station that the operator is assigned to
        self.operatorAssignedTo=None
        # the station the operator currently operating
        self.workingStation=None
        
        # variables to be used by OperatorRouter
        self.candidateEntities=[]               # list of the entities requesting the operator at a certain simulation Time
        self.candidateEntity=None               # the entity that will be chosen for processing
        self.candidateStations=[]               # list of candidateStations of the stations (those stations that can receive an entity)
        
        self.schedule=[]                        # the working schedule of the resource, the objects the resource was occupied by and the corresponding times
        
    @staticmethod
    def getSupportedSchedulingRules():
        return ("FIFO", "Priority", "WT", "EDD", "EOD",
            "NumStages", "RPC", "LPT", "SPT", "MS", "WINQ")
    
    #===========================================================================
    # assign an operator
    #===========================================================================
    def assignTo(self, callerObject=None):
        assert callerObject!=None, 'the operator cannot be assigned to None'
        self.operatorAssignedTo=callerObject
    
    #===========================================================================
    # un-assign an operator
    #===========================================================================
    def unAssign(self):
        self.operatorAssignedTo=None
    
    #===========================================================================
    # check whether the operator is assigned
    #===========================================================================
    def isAssignedTo(self):
        return self.operatorAssignedTo
    
    #===========================================================================
    # check whether the operator has only one candidateStation to work for
    #===========================================================================
    def hasOneOption(self):
        return len(self.candidateStations)==1
    
    #=======================================================================
    # findCandidateEntities method finding the candidateEntities of the operator  
    #=======================================================================
    def findCandidateEntities(self, pendingEntities=[]):
        if pendingEntities:
            for entity in [x for x in pendingEntities if x.canProceed and x.manager==self]:
                self.candidateEntities.append(entity)
    
    #===========================================================================
    # method that finds a candidate entity for an operator 
    #===========================================================================
    def findCandidateStation(self):
        from Globals import G
        router=G.Router
        candidateStation=next(x for x in self.candidateStations if not x in router.conflictingStations)
        if not router.sorting:
            if not candidateStation:
                candidateStation=next(x for x in self.candidateStations)
                router.conflictingStations.append(candidateStation)
        return candidateStation
    
    #===========================================================================
    # recursive method that searches for entities with available receivers
    #===========================================================================
    def findAvailableEntity(self):
        from Globals import G
        router=G.Router
        # if the candidateEntities and the entitiesWithOccupiedReceivers lists are identical then return None 
        if len(set(self.candidateEntities).intersection(router.entitiesWithOccupiedReceivers))==len(self.candidateEntities):
            return None
        availableEntity=next(x for x in self.candidateEntities if not x in router.entitiesWithOccupiedReceivers)
        receiverAvailability=False
        if availableEntity:
            for receiver in availableEntity.candidateReceivers:
                if not receiver in router.occupiedReceivers:
                    receiverAvailability=True
                    break
            # if there are no available receivers for the entity
            if not receiverAvailability:
                router.entitiesWithOccupiedReceivers.append(availableEntity)
                return self.findAvailableEntity()
        return availableEntity
    
    #===========================================================================
    # method that finds a candidate entity for an operator
    #===========================================================================
    def findCandidateEntity(self):
        from Globals import G
        router=G.Router
        # pick a candidateEntity
        candidateEntity=self.findAvailableEntity()
        if not router.sorting:
            if not candidateEntity:
                candidateEntity=next(x for x in self.candidateEntities)
                router.conflictingEntities.append(candidateEntity)
        return candidateEntity
        
    # =======================================================================
    #    sorts the candidateEntities of the Operator according to the scheduling rule
    # TODO: find a way to sort machines or candidate entities for machines, 
    #       now picks the machine that waits the most
    # =======================================================================
    def sortCandidateEntities(self):
        from Globals import G
        router=G.Router
        candidateMachines=self.candidateStations
        # for the candidateMachines
        if candidateMachines:
            # choose the one that waits the most time and give it the chance to grasp the resource
            for machine in candidateMachines:
                machine.critical=False
                if machine.broker.waitForOperator:
                    machine.timeWaiting=self.env.now-machine.broker.timeWaitForOperatorStarted
                else:
                    machine.timeWaiting=self.env.now-machine.timeLastEntityLeft
                # find the stations that hold critical entities
                if self in router.preemptiveOperators:
                    for entity in station.getActiveObjectQueue():
                        if entity.isCritical:
                            machine.critical=True
                            break
        # sort the stations according their timeWaiting
        self.candidateStations.sort(key= lambda x: x.timeWaiting, reverse=True)
        # sort the stations if they hold critical entities
        self.candidateStations.sort(key=lambda x: x.critical, reverse=False)
#         # TODO: have to consider what happens in case of a critical order
#         #if we have sorting according to multiple criteria we have to call the sorter many times
#         if self.schedulingRule=="MC":
#             for criterion in reversed(self.multipleCriterionList):
#                self.activeCandidateQSorter(criterion=criterion) 
#         #else we just use the default scheduling rule
#         else:
#             print self.schedulingRule
#             self.activeCandidateQSorter(self.schedulingRule)
    

    # =======================================================================
    #    sorts the Entities of the Queue according to the scheduling rule
    # =======================================================================
    def activeCandidateQSorter(self, criterion=None):
    # TODO: entityToGet is not updated for all stations, consider using it for all stations or withdraw the idea
    # TODO: sorting candidateStations is strange. some of them are waiting to get an entity, others are waiting for operator while holding an entity
        activeObjectQ=self.candidateStations
        if criterion==None:
            criterion=self.schedulingRule           
        #if the schedulingRule is first in first out
        if criterion=="FIFO": 
            # FIFO sorting has no meaning when sorting candidateEntities
            self.activeCandidateQSorter('WT')
            # added for testing
#             print 'there is no point of using FIFO scheduling rule for operators candidateEntities,\
#                     WT scheduling rule used instead'
        #if the schedulingRule is based on a pre-defined priority
        elif criterion=="Priority":
            activeObjectQ.sort(key=lambda x: x.identifyEntityToGet().priority)
        #if the scheduling rule is time waiting (time waiting of machine
        # TODO: consider that the timeLastEntityEnded is not a 
        #     indicative identifier of how long the station was waiting
        elif criterion=='WT':
            activeObjectQ.sort(key=lambda x: x.identifyEntityToGet().schedule[-1][1])
        #if the schedulingRule is earliest due date
        elif criterion=="EDD":
            activeObjectQ.sort(key=lambda x: x.identifyEntityToGet().dueDate)   
        #if the schedulingRule is earliest order date
        elif criterion=="EOD":
            activeObjectQ.sort(key=lambda x: x.identifyEntityToGet().orderDate)
        #if the schedulingRule is to sort Entities according to the stations they have to visit
        elif criterion=="NumStages":
            activeObjectQ.sort(key=lambda x: len(x.identifyEntityToGet().remainingRoute), reverse=True)  
        #if the schedulingRule is to sort Entities according to the their remaining processing time in the system
        elif criterion=="RPC":
            for object in activeObjectQ:
                entity=object.identifyEntityToGet()
                RPT=0
                for step in entity.remainingRoute:
                    processingTime=step.get('processingTime',None)
                    if processingTime:
                        RPT+=float(processingTime.get('mean',0))           
                entity.remainingProcessingTime=RPT
            activeObjectQ.sort(key=lambda x: x.identifyEntityToGet().remainingProcessingTime, reverse=True)     
        #if the schedulingRule is to sort Entities according to longest processing time first in the next station
        elif criterion=="LPT":
            for object in activeObjectQ:
                entity=object.identifyEntityToGet()
                processingTime = entity.remainingRoute[0].get('processingTime',None)
                entity.processingTimeInNextStation=float(processingTime.get('mean',0))
                if processingTime:
                    entity.processingTimeInNextStation=float(processingTime.get('mean',0))
                else:
                    entity.processingTimeInNextStation=0
            activeObjectQ.sort(key=lambda x: x.identifyEntityToGet().processingTimeInNextStation, reverse=True)             
        #if the schedulingRule is to sort Entities according to shortest processing time first in the next station
        elif criterion=="SPT":
            for object in activeObjectQ:
                entity=object.identifyEntityToGet()
                processingTime = entity.remainingRoute[0].get('processingTime',None)
                if processingTime:
                    entity.processingTimeInNextStation=float(processingTime.get('mean',0))
                else:
                    entity.processingTimeInNextStation=0
            activeObjectQ.sort(key=lambda x: x.identifyEntityToGet().processingTimeInNextStation) 
        #if the schedulingRule is to sort Entities based on the minimum slackness
        elif criterion=="MS":
            for object in activeObjectQ:
                object.identifyEntityToGet()
                RPT=0
                for step in entity.remainingRoute:
                    processingTime=step.get('processingTime',None)
                    if processingTime:
                        RPT+=float(processingTime.get('mean',0))              
                entity.remainingProcessingTime=RPT
            activeObjectQ.sort(key=lambda x: (x.identifyEntityToGet().dueDate-x.identifyEntityToGet().remainingProcessingTime))  
        #if the schedulingRule is to sort Entities based on the length of the following Queue
        elif criterion=="WINQ":
            from Globals import G
            for object in activeObjectQ:
                entity=object.identifyEntityToGet()
                nextObjIds=entity.remainingRoute[1].get('stationIdsList',[])
                for obj in G.ObjList:
                    if obj.id in nextObjIds:
                        nextObject=obj
                entity.nextQueueLength=len(nextObject.getActiveObjectQueue())           
            activeObjectQ.sort(key=lambda x: x.identifyEntityToGet().nextQueueLength)
        else:
            assert False, "Unknown scheduling criterion %r" % (criterion, )
            
    # =======================================================================    
    #            actions to be taken after the simulation ends
    # =======================================================================
    def postProcessing(self, MaxSimtime=None):
        if MaxSimtime==None:
            from Globals import G
            MaxSimtime=G.maxSimTime
        # if the repairman is currently working we have to count the time of this work    
#         if len(self.getResourceQueue())>0:
        if not self.checkIfResourceIsAvailable():
            self.totalWorkingTime+=self.env.now-self.timeLastOperationStarted
                
        # Repairman was idle when he was not in any other state
        self.totalWaitingTime=MaxSimtime-self.totalWorkingTime   
        # update the waiting/working time percentages lists
        self.Waiting.append(100*self.totalWaitingTime/MaxSimtime)
        self.Working.append(100*self.totalWorkingTime/MaxSimtime)
    
    # =======================================================================
    #                    outputs data to "output.xls"
    # =======================================================================
    def outputResultsXL(self, MaxSimtime=None):
        from Globals import G
        if MaxSimtime==None:
            MaxSimtime=G.maxSimTime
        # if we had just one replication output the results to excel
        if(G.numberOfReplications==1): 
            G.outputSheet.write(G.outputIndex,0, "The percentage of working of "+self.objName +" is:")
            G.outputSheet.write(G.outputIndex,1,100*self.totalWorkingTime/MaxSimtime)
            G.outputIndex+=1
            G.outputSheet.write(G.outputIndex,0, "The percentage of waiting of "+self.objName +" is:")
            G.outputSheet.write(G.outputIndex,1,100*self.totalWaitingTime/MaxSimtime)
            G.outputIndex+=1
        #if we had multiple replications we output confidence intervals to excel
            # for some outputs the results may be the same for each run (eg model is stochastic but failures fixed
            # so failurePortion will be exactly the same in each run). That will give 0 variability and errors.
            # so for each output value we check if there was difference in the runs' results
            # if yes we output the Confidence Intervals. if not we output just the fix value    
        else:
            G.outputSheet.write(G.outputIndex,0, "CI "+str(G.confidenceLevel*100)+"% for the mean percentage of Working of "+self.objName +" is:")
            if self.checkIfArrayHasDifValues(self.Working): 
                G.outputSheet.write(G.outputIndex,1,stat.bayes_mvs(self.Working, G.confidenceLevel)[0][1][0])
                G.outputSheet.write(G.outputIndex,2,stat.bayes_mvs(self.Working, G.confidenceLevel)[0][0])
                G.outputSheet.write(G.outputIndex,3,stat.bayes_mvs(self.Working, G.confidenceLevel)[0][1][1])  
            else: 
                G.outputSheet.write(G.outputIndex,1,self.Working[0])
                G.outputSheet.write(G.outputIndex,2,self.Working[0])
                G.outputSheet.write(G.outputIndex,3,self.Working[0])                            
            G.outputIndex+=1
            G.outputSheet.write(G.outputIndex,0, "CI "+str(G.confidenceLevel*100)+"% for the mean percentage of Waiting of "+self.objName +" is:")            
            if self.checkIfArrayHasDifValues(self.Waiting):
                G.outputSheet.write(G.outputIndex,1,stat.bayes_mvs(self.Waiting, G.confidenceLevel)[0][1][0])
                G.outputSheet.write(G.outputIndex,2,stat.bayes_mvs(self.Waiting, G.confidenceLevel)[0][0])
                G.outputSheet.write(G.outputIndex,3,stat.bayes_mvs(self.Waiting, G.confidenceLevel)[0][1][1])
            else: 
                G.outputSheet.write(G.outputIndex,1,self.Waiting[0])
                G.outputSheet.write(G.outputIndex,2,self.Waiting[0])
                G.outputSheet.write(G.outputIndex,3,self.Waiting[0]) 
            G.outputIndex+=1
        G.outputIndex+=1

       # =======================================================================
    #                    outputs results to JSON File
    # =======================================================================
    def outputResultsJSON(self):
        from Globals import G
        from Globals import getConfidenceIntervals
        json = {'_class': 'Dream.%s' % self.__class__.__name__,
                'id': self.id,
                'family': self.family,
                'results': {}}
        if(G.numberOfReplications==1):
            json['results']['working_ratio']=100*self.totalWorkingTime/G.maxSimTime
            json['results']['waiting_ratio']=100*self.totalWaitingTime/G.maxSimTime
        else:
            json['results']['working_ratio'] = getConfidenceIntervals(self.Working)
            json['results']['waiting_ratio'] = getConfidenceIntervals(self.Waiting)
        G.outputJSON['elementList'].append(json)
        