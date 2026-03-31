#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mar 2021

HTC_driver_v4
Tested @ Ubuntu 19.04, it should work with Windows, but with no guarantee.

Bux fix report:
    v4:
        fixed temp jump at the end of the ramping process
        add temp step control to mitigate temp overshooting to protect the crystal

Example:
    Ramping to 45°C, tty0, max safe step 2°C/min:
        HTC = HTC_driver(0,2)
        HTC.Ramping(45)


@author: Martin Bielak
"""
import serial
import time
import numpy as np
import copy
import platform
#import B57551G1103

import matplotlib.pyplot as plt
from IPython import get_ipython
get_ipython().run_line_magic('matplotlib', 'qt')


class HTC_driver:
    def __init__(self, htcPort, safeStep, vRef = 0, iBias = 0): #Constructor with parametter
        """Init HTC driver.
    
        Args:
            * htcPort (int) - HTC TTy port
            * safeStep - safe step in °C/min
            * optional 
                ** vRef (int) - vRef value., if not set, it will read it from HTC
                ** iBias - iBias value, if not set, it will read it from HTC

        """
        OS = platform.system()
        if OS == 'Linux':
            print ('OS = Linux')
            self.HTC = serial.Serial('/dev/ttyUSB'+str(htcPort), baudrate=115200, bytesize=serial.EIGHTBITS,stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, timeout=1)# rtscts=True
        elif OS == 'Windows':
            print ('OS = Windows')
            self.HTC = serial.Serial('COM'+str(htcPort), baudrate=115200, bytesize=serial.EIGHTBITS,stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, timeout=1)
        else:
            print ('OS ???')

        self.HTC.flush()
        self.HTC.readlines()
        try:
            self.HTC.write(("get setpoint\r\n").encode())
            out = ""
            while out != "setpoint":
                out = self.HTC.readline().decode().strip().split(' ')[0]
        except:
            print ('Init ERROR')
        
        self.vRef = vRef
        self.iBias = iBias
        self.safeStep = safeStep
        print ('Init OK')
        
    def __del__(self): # body of destructor
        """Close HTC driver.
        """
        iD = self.GetID(False)[0]
        self.HTC.close()
        print ("HTC " +str(iD) + " - serial port closed")

    def SerialCom(self, string):
        self.HTC.flush()
        self.HTC.write((str(string) + "\r\n").encode())
        out = self.HTC.readline().decode().strip()
        return (out)
        
###########################################################
###                                                        ###
###                          Math                          ###
###                                                        ###
###########################################################
    
    def R_to_T(self, R):
        """Return temperature corresponding to a given resistance.
    
        Args:
            * R (float): Resistance (in Ω).
    
        Returns:
            * float T: Temperature at resistance `R` (in C).
        """
        BETA = self.GetB()
        R25 = self.GetR25()
        #print (BETA)
        #print (R25)
        T = BETA/np.log(R/(R25*np.exp(-BETA/(25 + 273.15))))
        return (T - 273.15)
    
    def T_to_R(self, t):
        """Return resistance corresponding to a given temperature.
    
        Args:
            * t (float): Temperature in C.
    
        Returns:
            * float R: Resistance at temperature `T` (in Ω).
        """
        BETA = self.GetB()
        R25 = self.GetR25()
        #print (BETA)
        #print (R25)
        R = R25*np.exp(BETA*(1/(t + 273.15)-1/(25 + 273.15)))
        return (R)

    def RToSetPoint(self, r):
        '''    Convert R to SetPoint
        imput - R 
        output = SetPoint
        '''
        if self.iBias == 0:
            iBias = self.GetIbias()
        else:
            iBias = self.iBias*10**(-6)
        if self.vRef == 0:
            vRef = self.GetVref()
        else:
            vRef = self.vRef
        setPoint = iBias*r*(2**18)/vRef
        setPoint = int(round(setPoint,0))
        return (setPoint)

    def SetPointToR(self, setPoint): 
        '''    Convert SetPoint to R
        imput - SetPoint
        output = R
        '''
        if self.iBias == 0:
            iBias = self.GetIbias()
        else:
            iBias = self.iBias*10**(-6)
        if self.vRef == 0:
            vRef = self.GetVref()
        else:
            vRef = self.vRef
        r = setPoint*vRef/(iBias*(2**18))
        return (r)

    def TempToSetPoint(self, t):
        '''    Convert t to SetPoint
        imput - t [°C], vRef (if 0, read prom HTC), iBias (if 0 read from HTC) 
        output = SetPoint
        '''
        #r = B57551G1103.T_to_R_v2(t)
        r = self.T_to_R(t)
        setPoint = self.RToSetPoint(r)
        return (setPoint)
    
    def SetPointToTemp(self, setPoint): 
        '''    Convert SetPoint to t
        imput - SetPoint, vRef (if 0, read prom HTC), iBias (if 0 read from HTC) 
        output = t[°C]
        '''
        r = self.SetPointToR(setPoint)
        #t = B57551G1103.R_to_T(r)
        t = self.R_to_T(r)
        return (t)

###########################################################
###                                                        ###
###                    Get data from HTC                    ###
###                                                        ###
###########################################################
    def GetSetPoint(self):
        """Return set setpoint.
    
        Args:
            * 
    
        Returns:
            * setPoint (int) - setpoint
        
        MD: get setpoint - vrátí aktuálně zapsaný setpoint např. "setpoint 123456\r\n"
        """
        string = "get setpoint"
        setPoint = self.SerialCom(string)
        setPoint = int (setPoint.replace('setpoint ', ''))
        return (setPoint)
    
    def GetIlim(self):
        """Return set I limit.
    
        Args:
    
        Returns:
            * ilim (int) - I limit <0;7>
        
        MD: get ilim - vrátí aktuálně nastavený proudový limit jako číslo 0 až 7. Např. "ilim 1\r\n"
        """
        string = "get ilim"
        ilim = self.SerialCom(string)
        ilim = int (ilim.replace('ilim ', ''))
        return (ilim)
    
    def GetCint(self):
        """Return C integ value.
    
        Args:
    
        Returns:
            * cint (int) - C integ. <0;3>
        
        MD: get cint - vrátí aktuálně nastavený integrační kondenzátor jako číslo 0(OFF) až 3. Např. "cint 1\r\n"
        """
        string = "get cint"
        cint = self.SerialCom(string)
        cint = int (cint.replace('cint ', ''))
        return (cint)
    
    def GetRprop(self):
        """Return R prop.
    
        Args:
            *
    
        Returns:
            * rprop (int) - R prop.
        
        MD: get rprop - vrátí aktuální nastavení potnciometru pro proporční člen (gain) jako číslo 0 až 5115. Např. "rprop 5115\r\n"
        """
        string = "get rprop"
        rprop = self.SerialCom(string)
        rprop = int (rprop.replace('rprop ', ''))
        return (rprop)
    
    def GetB(self):
        """Return B parametter
    
        Args:
            *
    
        Returns:
            * b (int) - B parametter.
        
        MD: get B - vrátí aktuálně nastavený parametr B. Např. "B 3942\r\n"
        """
        string = "get B"
        b = self.SerialCom(string)
        b = int (b.replace('B ', ''))
        return (b)
    
    def GetR25(self):
        """Return R25 parametr (R@25°C)
    
        Args:
            * 
    
        Returns:
            * R25 (int) - R25 parametr (R@25°C)
        
        MD: get R0 - vrátí aktuálně nastavený parametr R25. Např. "R0 10000\r\n"
        """
        string = "get R0"
        R25 = self.SerialCom(string)
        R25 = int (R25.replace('R0 ', ''))
        return (R25)
    
    def GetADC(self):
        """Return V_termistor, I_act and V_act array
    
        Args:
            * 
    
        Returns:
            * array (int) - [V_termistor, I_act, V_act]
        
        MD: get adc - vrátí surové hodnoty přečtené ze všech vstupů ve formátu: "act x, i x, v x\r\n", kde 
            act je aktuální napětí na termistoru (výstup z ACTMON HTC modulu) a spočte se jako u=3.3x/4096, 
            i je aktuální proud a spočte se (asi) jako i=3.3x/40960.010638 
            v je aktuální napětí a spočte se asi jako v=(3.3x/4096)*4.7037 (spolu s proudem a odporem peltieru dává informaci o ztrátovém výkon)
        """
        string = "get adc"
        out = self.SerialCom(string)
        act = int (out.split(', ')[0].split(' ')[1])
        i = int (out.split(', ')[1].split(' ')[1])
        v = int (out.split(', ')[2].split(' ')[1])
        act = 3.3*act/4096
        i = 3.3*i/40960.010638
        v=(3.3*v/4096)*4.7037
        return ([act,i,v])
    
    def GetIbias(self):
        """Return I bias.
    
        Args:
            * 
    
        Returns:
            * iBias - I bias (A)
        
        MD: get ibias - vrátí konstantu i_bias. Např. "ibias 26uA\r\n"
        """
        #Doplnit s novou verzí FW
        #iBias = 224 #iBias in uA
        #iBias = iBias*10**(-6)
        #return iBias
        string = "get ibias"
        iBias = self.SerialCom(string)
        iBias = iBias.replace('uA', '')
        iBias = int (iBias.replace('ibias ', ''))
        iBias = iBias*10**(-6)
        return (iBias)
    
    
    def GetTempR(self): 
        """Return actual R [Ω] and t [°C].
    
        Args:
    
        Returns:
            * [R,t] (array) - R [Ω], t (°C)
        
        MD: 
        """
        if self.iBias == 0:
            iBias = self.GetIbias()
        else:
            iBias = iBias*10**(-6)
        r = self.GetADC()[0]/iBias
        #t = B57551G1103.R_to_T(r)
        t = self.R_to_T(r)
        return ([r,t])
    
    def GetVref(self):
        """Return V ref.
    
        Args:
            * 
    
        Returns:
            * vRef - V ref in (V)
        
        MD: get vref - vrátí konstantu vref. Např. "vref 3300mV\r\n" 
        """
        #Doplnit s novou verzí FW
        #vRef = 3.3 #vRef in V
        #return vRef
        
        string = "get vref"
        vRef = self.SerialCom(string)
        vRef = vRef.replace('mV', '')
        vRef = int (vRef.replace('vref ', ''))
        vRef = vRef*10**(-3)
        return (vRef)
    
    def GetStartup(self, printFlag = True):
        """Return startup state.
    
        Args:
            * optional: 
                ** printFlag - if True, print startup status
    
        Returns:
            * startup status
        
        MD: get startup - vrátí startup režim Např. "startup hold R\r\n" nebo "startup hold setpoint\r\n"
            STARTUP - volí "startup režim". "Hold R" znamená změř po startu aktuální napětí na termistoru, přepiš setpoint na hodnotu která odpovídá přibližně stejnému napětí a ten drž. "Hold Setpoint" znamená, načti z paměti uloženou hodnotu setpointu a tu drž. 
        """
        #Doplnit s novou verzí FW
        #vRef = 3.3 #vRef in V
        #return vRef
        string = "get startup"
        startupStatus = self.SerialCom(string)
        if printFlag == True:
            print (startupStatus)
        return (startupStatus)
    
    def GetSetTempR(self):
        """Return set parameters
    
        Args:
    
        Returns:
            * setPoint, setPointT, setPointR - Target/set values
        
        MD: 
        """
        setPoint = self.GetSetPoint()
        setPointT = self.SetPointToTemp(setPoint)
        setPointR = self.SetPointToR(setPoint)
        return ([setPoint, setPointT, setPointR])
    
    def GetID(self, printFlag = True):
        """Return ID and FW ver.
    
        Args:
            * optional: 
                ** printFlag - if True, print ID and FW ver
    
        Returns:
            * ID
            * FW ver
        
        MD: get id - vrátí seriové číslo zařízení jako např "id 3\r\n" - mělo by korespondovat s číslem na kastli, pokud nesedí informujte mě
             fwver vrátí verzi firmwaru ve formátu např. "1.1\r\n"
        """
        #Doplnit s novou verzí FW
        #vRef = 3.3 #vRef in V
        #return vRef
        string = "get id"
        iD = self.SerialCom(string)
        string = "get fwver"
        fwVer = self.SerialCom(string)
        if printFlag == True:
            print ("Serial number: \t" + str(iD))
            print ("FW ver: \t\t\t" + str(fwVer))
        return ([iD,fwVer])
    
###########################################################
###                                                        ###
###                         Set HTC                        ###
###                                                        ###
###########################################################

    def SetSetPoint(self, dacVall):
        """Set new target setpoint.
    
        Args:
            * dacVall (int) - new target SetPoint
    
        Returns:
            * out - HTC response
        
        MD: set dac x - zapíše hodnotu x jako setpoint 
            SETPOINT - volí napětí DA převodníku řídícího setpoint. Rozsah je 0 až 2^18-1 a lineárně pokrývá napětí 3.3V. Napětí lze spočítat jako u=3.3*value/262144. Odpor termistoru pak jako R=u/i_bias. Hodnotu i_bias má každý driver individuální
        """
        try:
            dacVall = np.round(dacVall)
            dacVall = int(dacVall)
        except:
            return (0)
        string = 'set dac '+str(dacVall)
        out = self.SerialCom(string)
        return (out)
    
    def SetRprop(self, rpropVall):
        """Set new R prop.
    
        Args: 
            * rpropVall (int) - new R prop.
    
        Returns:
            * out - HTC response
        
        MD: set rprop x - zapíše hodnotu x jako RPROP 
            PROP - nastavení proporčního členu / zisku. RAW hodnota je v rozsahu 0 až 5115 a odpovídá odporu ~1.6k až ~500k. Orientační hodnota odporu i odpovídajícího zisku je zobrazena v pravé části displeje.
        """
        try:
            rpropVall = int(rpropVall)
        except:
            return (0)
        string = 'set rprop '+str(rpropVall)
        out =  self.SerialCom(string)
        return (out)
    
    def SetIlim(self, ilimVall):
        """Set new I lim.
    
        Args: 
            * ilimVall (int) - new I limit.
    
        Returns:
            * out - HTC response
        
        MD: set ilim x - zapíše hodnotu 0 až 7 kterou se volí proudový limit 
            ILIM - volí jednu z osmi hodnot proudového limitu. Jedná se o orientační hodnoty s tím že vyšší hodnoty by měly být přesnější.
        """
        try:
            ilimVall = int(ilimVall)
        except:
            return (0)
        string = 'set ilim '+str(ilimVall)
        out =  self.SerialCom(string)
        return (out)
    
    def SetCint(self, cintVall):
        """Set new C integ.
    
        Args:
            * cintVall (int) - new C integ.
    
        Returns:
            * out - HTC response
        
        MD: set cint x - zapíše hodnotu 0 až 3 kterou se volí integrační kondenzátor 
            CINT - volí jeden ze tří integračních kondenzátorů (a žádného). Orientační integrační čas je v pravé polovině displeje
        """
        try:
            cintVall = int(cintVall)
        except:
            return (0)
        string = 'set cint '+str(cintVall)
        out =  self.SerialCom(string)
        return (out)
    
    def SetR25(self, R25Vall):
        """Set new R25 value (R@25°C).
    
        Args:
            * R25Vall (int) - new R25.
    
        Returns:
            * out - HTC response
        
        MD: set R0 - zapíše hodnotu parametru R25 - zadává se v ohmech v rozmezí 400 až 50000 
            PARAM R25 - volí odpor termistoru při teplotě 25°C (tato hodnota slouží k orientačním výpočtům v "Overwiev"), vstupní rozsah je 0.4k až 50k.
        """
        try:
            R25Vall = int(R25Vall)
        except:
            return (0)
        string = 'set R0 '+str(R25Vall)
        out =  self.SerialCom(string)
        return (out)
    
    def SetB(self, bVall):
        """Set new B parametter.
    
        Args:
            * bVall (int) - new B param.
    
        Returns:
            * out - HTC response
        
        MD: zapíše hodnotu parametru B 
            PARAM B - volí B konstantu termistoru (tato hodnota slouží k orientačním výpočtům v "Overwiev"), vstupní rozsah je 2000 až 8000. 
        """
        try:
            bVall = int(bVall)
        except:
            return (0)
        string = 'set B '+str(bVall)
        out =  self.SerialCom(string)
        return (out)
    
    def SetStartup(self, startupStatus):
        """Return startup state.
    
        Args:
            * 
            * startupStatus (int)     - 0 - Hold R
                                    - 1 - Hold setpoint
    
        Returns:
            * out - HTC response
        
        MD: set startup - zvolí startup režim, hodnota 0 => Hold R, hodnota 1 => Hold Setpoint (viz manuální ovládání) 
            STARTUP - volí "startup režim". "Hold R" znamená změř po startu aktuální napětí na termistoru, přepiš setpoint na hodnotu která odpovídá přibližně stejnému napětí a ten drž. "Hold Setpoint" znamená, načti z paměti uloženou hodnotu setpointu a tu drž. 
        """
        try:
            startupStatus = int(startupStatus)
        except:
            return (0)
        string = 'set startup '+str(startupStatus)
        out =  self.SerialCom(string)
        return (out)


    def SetTemp(self, t, printFlag = False):
        """Set new target temp.
    
        Args:
            * t (float) - target temp [°C]
            * optional: 
                ** printFlag (bool) - print HTC response
    
        Returns:
            * SetPoint, t, r - SetPoint (DAC vall), t [°C], r[Ω]
        
        MD:
        """
        setPoint = self.TempToSetPoint(t)
        flag = self.SetSetPoint(setPoint)
        r = self.SetPointToR(setPoint)
        if printFlag == True:
            print (flag)
        return ([setPoint, t, r]) #return (setPoint, t, r)

###########################################################
###                                                        ###
###                           Save                           ###
###                                                        ###
###########################################################
    
    def Save(self, printFlag = True):
        """Save actual setings to EPROM.
    
        Args:
            * optional: 
                ** printFlag (bool) - print saved parametters
    
        Returns:
            *
        
        MD: save - uloží nastavené parametry do paměti (odkud se vyvolají po startu)
        """
        string = 'save'
        self.SerialCom(string)
        if printFlag == True:
            cInt = self.GetCint()
            r25 = self.GetR25()
            b = self.GetB()
            setPoint = self.GetSetPoint()
            setTempR = self.GetSetTempR()
            startUp = self.GetStartup(False)
            iLim = self.GetIlim()
            rProp = self.GetRprop()
            print ("C integ. = \t\t " + str(cInt))
            print ("R25 = \t\t\t " + str(r25))
            print ("B = \t\t\t\t " + str(b))
            print ("I lim. = \t\t " + str(iLim))
            print ("R prop. = \t\t " + str(rProp))
            print ("Setpoint = \t\t " + str(setPoint))
            print ("Set R, t = \t\t " + str(np.round(setTempR[2])/1000) + " kΩ \t" + str(np.round(setTempR[1])) + " °C")
            print ("Startup = \t\t " + str(startUp))
            
###########################################################
###                                                        ###
###                         Ramping                        ###
###                                                        ###
###########################################################
    
    def Ramping(self, tTarget): 
        """Set new target temp. It cycling "temp step" -> sleep(5) -> "temp step", where "temp step" = max safe step per 5s
    
        Args:
            * tTarget - target t [°C]
        Returns:
            * 
        """
        sleep = 5 #in sec
        safeStep05 = self.safeStep/2*sleep/60
        tAct = self.GetTempR()[1]
        t = tAct
        #print (tAct)
        #print (tTarget-safeStep05)
        maxSteps = (np.abs(tAct-tTarget)/safeStep05)*1.5
        if maxSteps < 10:
            maxSteps = 10
        i = 0
        #print (maxSteps)
        predTime = np.round((np.abs(tAct-tTarget)/safeStep05)*sleep/60,1)
        print ("Have a rest for " + str(predTime) + " min :)")
        #print (maxSteps)
        timeStart = time.time()
        tStart = tAct
        flag = False
        
        if tTarget > tAct:
            print ('Ramping UP')
            #t = 100
            direction = 1
        elif tTarget < tAct:
            print ('Ramping DOWN')
            #t = 0
            direction = -1
        else:
            print ('Some error, or tAct = tTarget')
            return (0)
            
        #while ( tTarget + (-1*direction) * safeStep05 > tAct  and i <= maxSteps):
        while ( direction * tTarget > direction * (tAct + direction * safeStep05)  and i <= maxSteps):
            tAct = self.GetTempR()[1]
            if abs(tAct - t) > 2*safeStep05:
                t = t
            elif direction * (tAct + direction * safeStep05) < direction * t and abs(tAct - t) < 2*safeStep05:
                t = tAct + direction * safeStep05 * 2
                print ('If - ' + str(i))
                startTime = time.time()
                while time.time()-startTime < 5 * sleep:
                    actTemp = self.GetTempR()
                    print (f'\rAct. setpoint is: {np.round(t,2)}°C\t Act. temp is: {np.round(actTemp[1],2)}°C\t ', end='')
            else:
                t = tAct + direction * safeStep05
            i = i+1
            self.SetTemp(t)
            startTime = time.time()
            while time.time()-startTime < sleep:
                actTemp = self.GetTempR()
                print (f'\rAct. setpoint is: {np.round(t,2)}°C\t Act. temp is: {np.round(actTemp[1],2)}°C\t ', end='')
            #time.sleep(sleep)
            #print (i)
            #if tAct > tTarget-safeStep05:
                #break
            tAct = self.GetTempR()[1]
            
        if i < maxSteps:
            tGrad = (self.GetTempR()[1] - tStart)/((time.time() - timeStart)/60)
            startTime = time.time()
            while time.time()-startTime < 2*sleep:
                actTemp = self.GetTempR()
                print (f'\rAct. setpoint is: {np.round(t,2)}°C\t Act. temp is: {np.round(actTemp[1],2)}°C\t ', end='')
        
            print (f'\nTemp gradient was: {tGrad} °C/min\t ', end='')
            print ('\n i = ' + str(i) + '        limit was: ' + str(maxSteps))
            
            if np.abs(self.GetTempR()[1]-tTarget) < 1.2*safeStep05:
                print (f'Last step = {tTarget - self.GetTempR()[1]}°C.')
                self.SetTemp(tTarget)
                startTime = time.time()
                while time.time()-startTime < 5*sleep:
                    actTemp = self.GetTempR()
                    print (f'\rAct. setpoint is: {np.round(tTarget,2)}°C\t Act. temp is: {np.round(actTemp[1],2)}°C\t ', end='')
            
            else:
                flag = True
        else:
            tGrad = (self.GetTempR()[1] - tStart)/((time.time() - timeStart)/60)
            print (f'\rTemp gradient was: {tGrad} °C/min\t ', end='')
            
            if np.abs(self.GetTempR()[1]-tTarget) < 1.2*safeStep05:
                print ('\n i = ' + str(i) + '        limit was: ' + str(maxSteps))
                #print (f'Last step = {tTarget - self.GetTempR()[1]}°C.')
                flag = True
            else: 
                print ('\n i = ' + str(i) + '        limit was: ' + str(maxSteps))
                print ('Target setpoint cannot be reached, check iLim setting or PI.')
            
        if flag == True:
            print (f'\nLast step = {tTarget - self.GetTempR()[1]}°C, grad_lim is {self.safeStep}°C/min.')
            print (f'Actual temp is: {np.round(self.GetTempR()[1],2)}°C set point is: {np.round(self.GetSetTempR()[1],2)}°C target temp is: {np.round(tTarget,2)}°C')
            val = input('Do you want to set target temp as a new set point? (Y/N) or restart ramping (R)?')
            if val.lower() == 'y':
                self.SetTemp(tTarget)
                startTime = time.time()
                while time.time()-startTime < 5*sleep:
                    actTemp = self.GetTempR()
                    print (f'\rAct. setpoint is: {np.round(tTarget,2)}°C\t Act. temp is: {np.round(actTemp[1],2)}°C\t ', end='')
            elif val.lower() == 'r':
                self.Ramping(tTarget)
            else:
                pass
        print ('\nRamping - END')
    
    def StepResponse(self, targetTemp, targetTime, legend = False, plot=False, printFlag = False):
        """Plot response for temp step :)
    
        Args:
            * targetTemp - target temp for step response 
            * targetTime - ploting time
            * optional: 
                ** ledend - show it in legend
                ** printFlag - if True, print startup status
                ** 
    
        Returns:
            * times,data,targetTempData
        """
        #actTemp = GetTempR(HTC)[1]
        data = []
        targetTempData = []
        times = []
        start = time.time()
        initSetPoint = self.GetSetTempR()[0]
        tAct = self.GetTempR()[1]
        while (time.time()-start)<=targetTime:
            result = self.GetTempR()[1]
            #print(result)
            data.append(result)
            times.append(time.time()-start)
            targetTempData.append(self.GetSetTempR()[1])
            #plt.scatter(time.time()-start, result)
            if ((time.time()-start) > targetTime/10):
                self.SetTemp(targetTemp, printFlag)
            time.sleep(.1)
        #print (len(data))
        #print (len(time.time()-start))
        #print (len(targetTempData))
        #plt.axis([0, targetTime, actTemp-5, targetTemp+20])
        if plot==True: 
            if legend == False:
                plt.plot(times, data)
            else:
                plt.plot(times, data, label=str(legend))
            plt.plot(times, targetTempData)
            plt.legend()
            plt.show()
        #self.SetTemp(targetTempData[0], printFlag)
        self.SetSetPoint(initSetPoint)
        return([times,data,targetTempData])
    
    def AutoTuningPI(self, propMin, propMax, propStep, targetTemp, measTime = 120):
        """PI tuning :) - Without temp gradient check
    
        Args:
            * propMin
            * propMax
            * propStep
            * targetTemp for step response 
            * optional:
                *mesTime
    
        Returns:
            * [bestProp, bestInt, resultsProp, resultsCint]
        """
        predTime = (len(range(propMin, propMax+1, propStep))+4)*(measTime+measTime/3)/60
        print ("Have a rest for " + str(predTime) + " min :)")
        resultsProp = []
        self.SetCint(0)
        print ('Tunning prop')
        for prop in range(propMin, propMax+1, propStep):
            print (prop)
            self.SetRprop(prop)
            [times,data,targetTempData] = self.StepResponse(targetTemp, measTime, prop)
            suma = 0
            for i in range(int(len(targetTempData)/2),int(len(targetTempData))): 
                suma = suma + abs(targetTempData[i]-data[i])
            #results.append([prop,suma])
            resultsProp.append([prop,suma,times,data,targetTempData])
            time.sleep(measTime/3)
        bestProp = resultsProp[np.where(np.transpose(resultsProp)[1] == min(np.transpose(resultsProp)[1]))[0][0]][0]
        self.SetRprop(bestProp)
        
        resultsCint = []
        print ('Tunning cInt')
        toAppend = copy.deepcopy(resultsProp[np.where(np.transpose(resultsProp)[0] == bestProp)[0][0]])
        resultsCint.append(toAppend)
        #print (resultsProp)
        resultsCint[0][0]=0
        #print (resultsProp)
        #print (resultsCint)
        for cInt in range(1,4):
            print (cInt)
            self.SetCint(cInt)
            [times,data,targetTempData] = self.StepResponse(targetTemp, measTime)
            suma = 0
            for i in range(int(len(targetTempData)/2),int(len(targetTempData))): 
                suma = suma + abs(targetTempData[i]-data[i])
            #results.append([cInt,suma])
            resultsCint.append([cInt,suma,times,data,targetTempData])
            time.sleep(measTime/3)
            #plt.plot(times, data, label=str(cInt))
        bestInt = resultsCint[np.where(np.transpose(resultsCint)[1] == min(np.transpose(resultsCint)[1]))[0][0]][0]
        self.SetCint(bestInt)
        print ('Prop = ' + str(bestProp) + ' \t cInt = ' + str(bestInt))
        
        fig1, (ax1, ax2) = plt.subplots(nrows=1, ncols=2)
        fig1.suptitle('PI auto tuning :)')
        for dataPlot in resultsProp:
            ax1.plot(dataPlot[2], dataPlot[3], label=str(dataPlot[0]))
        ax1.plot(times, targetTempData)
        ax1.legend()
        ax1.title.set_text("prop tuning, cInt = 0")
        for dataPlot in resultsCint:
            ax2.plot(dataPlot[2], dataPlot[3], label=str(dataPlot[0]))
        ax2.plot(times, targetTempData)
        ax2.legend()
        ax2.title.set_text("cInt tuning, prop = " + str(bestProp))
        
        return ([bestProp, bestInt, resultsProp, resultsCint])
    