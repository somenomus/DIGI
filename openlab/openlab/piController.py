import numpy

class Controller(object):
    
    errorSum = 0  
    resetStatus = True
    measured = None
    referenceLast = 0

    def __init__(self, kp, ti, ts, reference, referenceMaxRateOfChange, initialOutput, isReversed,minOutput, maxOutput):
        print("Initializing PI Controller")
        self.kp = kp
        self.ti = ti
        self.ts = ts
        self.reference = reference
        self.referenceLast = reference
        self.referenceMaxRateOfChange = referenceMaxRateOfChange
        self.initialOutput = initialOutput
        
        if isReversed:
            self.isReversedFactor = -1
        else:
            self.isReversedFactor = 1;
            
        self.minOutput = minOutput
        self.maxOutput = maxOutput
        
        self.errorSum = initialOutput / (self.kp / self.ti) * self.isReversedFactor;
        
    def softReset(self):
            print("Resetting PI Controller")
            self.resetStatus = True
            self.referenceLast = self.reference
            self.errorSum = self.output / (self.kp / self.ti) * self.isReversedFactor;

    def reset(self, reference, measured):
        print("Resetting PI Controller")
        self.resetStatus = True
        self.reference = reference 
        self.referenceLast = reference
        self.output = measured
        self.errorSum = self.output / (self.kp / self.ti) * self.isReversedFactor;        
        
    def rateLimit(self, reference):     
         delta = reference - self.referenceLast
         sign = numpy.sign(delta)
         value = self.referenceLast + (sign * min(numpy.abs(delta), self.referenceMaxRateOfChange * self.ts))   
         return value;
    
    def getOutput(self,reference, measured):
        
        self.reference = self.rateLimit(reference)
        
        self.measured = measured
        if self.resetStatus:
            self.error = self.reference - self.measured
            self.referenceLast   = self.reference
            self.resetStatus = False
        else:
            self.error = self.reference - self.measured
           
        self.proportional = self.kp * self.isReversedFactor * self.error
        self.errorSum = self.errorSum  + (self.error * self.ts)
        self.integral = (self.kp / self.ti) * self.isReversedFactor * self.errorSum
            
        output = self.proportional + self.integral
        
        if  output >  self.maxOutput:
            output = self.maxOutput
            self.errorSum = output / (self.kp / self.ti) * self.isReversedFactor
            
        if  output < self.minOutput:
            output = self.minOutput
            self.errorSum = output / (self.kp / self.ti) * self.isReversedFactor

        self.referenceLast = self.reference
        self.output = output

        return output
