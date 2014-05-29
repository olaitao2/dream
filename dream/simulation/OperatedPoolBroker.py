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
Created on 27 Nov 2013

@author: Ioannis
'''
'''
Models an Interruption that handles the operating of a Station by an ObjectResource
'''

# from SimPy.Simulation import Process, Resource, SimEvent
import simpy
from ObjectInterruption import ObjectInterruption
# from SimPy.Simulation import waituntil, now, hold, request, release, waitevent

# ===========================================================================
#               Class that handles the Operator Behavior
# ===========================================================================
class Broker(ObjectInterruption):
    
    # =======================================================================
    #   according to this implementation one machine per broker is allowed
    #     The Broker is initiated within the Machine and considered as 
    #                black box for the ManPy end Developer
    # ======================================================================= 
    def __init__(self, operatedMachine):
        ObjectInterruption.__init__(self,operatedMachine)
        self.type = "Broker"
        # variables that have to do with timing
        self.timeOperationStarted = 0
        self.timeLastOperationEnded = 0
        self.timeWaitForOperatorStarted=0
        # Broker events
        self.isCalled=self.env.event()#SimEvent('brokerIsCalled')
        self.resourceAvailable=self.env.event()#SimEvent('resourceAvailable')
        self.waitForOperator=False
        
    #===========================================================================
    #                           the initialize method
    #===========================================================================
    def initialize(self):
        ObjectInterruption.initialize(self)
        self.timeLastOperationEnded=0
        self.timeOperationStarted=0
        self.timeWaitForOperatorStarted=0
        self.waitForOperator=False
        
    # =======================================================================
    #                          the run method
    # TODO: have to signal Router that broker is asking operator, and wait till the Router decides
    # =======================================================================    
    def run(self):
        while 1:
            # TODO: add new broker event - brokerIsCalled
            yield self.isCalled
            assert self.isCalled.value==self.env.now, 'the broker should be granted control instantly'
            self.isCalled=self.env.event()
            self.victim.printTrace(self.victim.id, received='(broker)')
    # ======= request a resource
            if self.victim.isOperated()\
                and any(type=='Load' or type=='Setup' or type=='Processing'\
                        for type in self.victim.multOperationTypeList):
                # update the time that the station is waiting for the operator
                self.timeWaitForOperatorStarted=self.env.now#()
                #===============================================================
                # if the victim already holds an entity that means that the machine's operation type
                #     is no Load or setup, in that case the router is already invoked and the machine is already assigned an operator
                from Globals import G
                if not self.victimQueueIsEmpty():
                    # add the currentEntity to the pendingEntities
                    if not self.victim.currentEntity in G.pendingEntities:
                        G.pendingEntities.append(self.victim.currentEntity)
                    if not G.Router.invoked:
                        self.victim.printTrace(self.victim.id, signal='router (broker)')
                        G.Router.invoked=True
                        G.Router.isCalled.succeed(self.env.now)
                       
                    self.waitForOperator=True
                    self.victim.printTrace(self.victim.id, waitEvent='(resourceIsAvailable broker)')
                    yield self.resourceAvailable
                    self.resourceAvailable=self.env.event()
                    # remove the currentEntity from the pendingEntities
                    if self.victim.currentEntity in G.pendingEntities:
                        G.pendingEntities.remove(self.victim.currentEntity)
                    self.waitForOperator=False
                    self.victim.printTrace(self.victim.id, resourceAvailable='(broker)')
                #===============================================================
                
                
                assert self.victim.operatorPool.checkIfResourceIsAvailable(), 'there is no available operator to request'
                # set the available resource as the currentOperator
                self.victim.currentOperator=self.victim.operatorPool.findAvailableOperator()
                
                
                with self.victim.operatorPool.getResource(self.victim.currentOperator).request() as request:
                    yield request
                    self.victim.printTrace(self.victim.currentOperator.objName, startWork=self.victim.id)
                    # clear the timeWaitForOperatorStarted variable
                    self.timeWaitForOperatorStarted = 0
                    # update the time that the operation started
                    self.timeOperationStarted = self.env.now#()
                    self.victim.outputTrace(self.victim.currentOperator.objName, "started work in "+ self.victim.objName)
                    self.victim.currentOperator.timeLastOperationStarted=self.env.now#()
                    # signal the machine that an operator is reserved
                    self.victim.brokerIsSet.succeed(self.env.now)
                    
                    # wait till the processing is over
                    yield self.isCalled
                    assert self.isCalled.value==self.env.now, 'the broker should be granted control instantly'
                    self.isCalled=self.env.event()
                
                # The operator is released
                    
                if not self.victim.isOperated():
                    self.victim.currentOperator.totalWorkingTime+=self.env.now-self.victim.currentOperator.timeLastOperationStarted                
                    # signal the other brokers waiting for the same operators that they are now free
                    # also signal the stations that were not requested to receive because the operator was occupied
                    
                    # TODO: signalling the router must be done more elegantly, router must be set as global variable
                    # if the router is already invoked then do not signal it again
                    if not self.victim.router.invoked:
                        self.victim.printTrace(self.victim.id, signal='router (broker)')
                        self.victim.router.invoked=True
#                         self.victim.router.isCalled.signal(now())
                        self.victim.router.isCalled.succeed(self.env.now)
                    # TODO: signalling the router will give the chance to it to take the control, but when will it eventually receive it. 
                    #     after signalling the broker will signal it's victim that it has finished it's processes 
                    # TODO: this wont work for the moment. The actions that follow must be performed by all operated brokers. 
                    
                    self.victim.printTrace(self.victim.currentOperator.objName, finishWork=self.victim.id)
                    # the victim current operator must be cleared after the operator is released
                    self.timeLastOperationEnded = self.env.now
                    self.victim.currentOperator = None
                else:
                    pass
                # return the control to the victim
                self.victim.brokerIsSet.succeed(self.env.now)
                
