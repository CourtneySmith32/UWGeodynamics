import json
from json import JSONEncoder
import underworld.function as fn
import numpy as np
from .scaling import UnitRegistry as u
from .scaling import nonDimensionalize as nd
from copy import copy
from collections import OrderedDict

def linearCohesionWeakening(cumulativeTotalStrain, Cohesion, CohesionSw, epsilon1=0.5, epsilon2=1.5, **kwargs):

    cohesionVal = [(cumulativeTotalStrain < epsilon1, fn.misc.constant(Cohesion)),
                   (cumulativeTotalStrain > epsilon2, fn.misc.constant(CohesionSw)),
                   (True, Cohesion + ((Cohesion - CohesionSw)/(epsilon1 - epsilon2)) * (cumulativeTotalStrain - epsilon1))]

    return fn.branching.conditional(cohesionVal)

def linearFrictionWeakening(cumulativeTotalStrain, FrictionCoef, FrictionCoefSw, epsilon1=0.5, epsilon2=1.5, **kwargs):

    frictionVal = [(cumulativeTotalStrain < epsilon1, fn.misc.constant(FrictionCoef)),
                   (cumulativeTotalStrain > epsilon2, fn.misc.constant(FrictionCoefSw)),
                   (True, FrictionCoef + ((FrictionCoef - FrictionCoefSw)/(epsilon1 - epsilon2)) * (cumulativeTotalStrain - epsilon1))]

    frictionVal = fn.branching.conditional(frictionVal)
 
    return fn.math.atan(frictionVal)


class ViscosityLimiter(object):

    def __init__(self, minViscosity, maxViscosity):

        self.minViscosity = minViscosity
        self.maxViscosity = maxViscosity

    def apply(self, viscosityField):
        maxBound = fn.misc.min(viscosityField, nd(self.maxViscosity))
        minMaxBound = fn.misc.max(maxBound, nd(self.minViscosity))
        return minMaxBound 


class Rheology(object):

    def __init__(self, pressureField=None, strainRateInvariantField=None,
                 temperatureField=None, viscosityLimiter=None, stressLimiter=None):

        self.pressureField = pressureField
        self.strainRateInvariantField = strainRateInvariantField
        self.temperatureField = temperatureField
        self._viscosity_limiter = viscosityLimiter
        self.stressLimiter = stressLimiter
        self.firstIter = True
        
        self.viscosity = None
        self.plasticity = None
        self.cohesion = None
        self.friction = None
        
        return


class _DruckerPragerEncoder(JSONEncoder):
    attributes = [
        "name",
        "cohesion",
        "frictionCoefficient",
        "cohesionAfterSoftening",
        "frictionAfterSoftening",
        "minimumViscosity",
        "epsilon1",
        "epsilon2"]
    
    def default(self, obj):
        d = {}

        for attribute in self.attributes:
            d[attribute] = str(obj[attribute])

        return d


class DruckerPrager(object):

    def __init__(self, name=None, cohesion=None, frictionCoefficient=None,
                 cohesionAfterSoftening = None,
                 frictionAfterSoftening = None,
                 minimumViscosity=None, plasticStrain=None, pressureField=None,
                 epsilon1=0.5, epsilon2=1.0):

        self.name = name
        self._cohesion = cohesion
        self._frictionCoefficient = frictionCoefficient
        self.cohesionAfterSoftening = cohesionAfterSoftening
        self.frictionAfterSoftening = frictionAfterSoftening
        
        self.minimumViscosity = minimumViscosity
        
        self.plasticStrain = plasticStrain
        self.pressureField = pressureField
        self.epsilon1 = epsilon1
        self.epsilon2 = epsilon2
        
        self.cohesionWeakeningFn = linearCohesionWeakening
        self.frictionWeakeningFn = linearFrictionWeakening

    def __getitem__(self, name):
        return self.__dict__[name]

    def _json_(self):
        return json.dumps(self, cls=_DruckerPragerEncoder)

    def to_json(self):
        attributes = [
            "name",
            "cohesion",
            "frictionCoefficient",
            "cohesionAfterSoftening",
            "frictionAfterSoftening",
            "minimumViscosity",
            "epsilon1",
            "epsilon2"]
        
        d = {}

        for attribute in attributes:
            d[attribute] = str(self[attribute])

        return d

    def _repr_html_(self):
        attributes  = OrderedDict()
        attributes["Cohesion"] = self.cohesion
        attributes["Cohesion After Softening"] = self.cohesionAfterSoftening
        attributes["Friction Coefficient"] = self.frictionCoefficient
        attributes["Friction Coefficient after Sotening"] = (
            self.frictionAfterSoftening)
        attributes["Epsilon 1"] = self.epsilon1
        attributes["Epsilon 2"] = self.epsilon2
        header = "<table>"
        footer = "</table>"
        html = ""
        for key, val in attributes.iteritems():
            html += "<tr><td>{0}</td><td>{1}</td></tr>".format(key, val)

        return header + html + footer      

    @property
    def cohesion(self):
        return self._cohesion

    @cohesion.setter
    def cohesion(self, value):
        self._cohesion = value

    @property
    def cohesionAfterSoftening(self):
        return self._cohesionAfterSoftening

    @cohesionAfterSoftening.setter
    def cohesionAfterSoftening(self, value):
        if value:
            self._cohesionAfterSoftening = value
        else:
            self._cohesionAfterSoftening = self.cohesion

    @property
    def frictionCoefficient(self):
        return self._frictionCoefficient
    
    @frictionCoefficient.setter
    def frictionCoefficient(self, value):
        self._frictionCoefficient = value
    
    @property
    def frictionAfterSoftening(self):
        return self._frictionAfterSoftening

    @frictionAfterSoftening.setter
    def frictionAfterSoftening(self, value):
        if value:
            self._frictionAfterSoftening = value
        else:
            self._frictionAfterSoftening = self.frictionCoefficient
    
    def _frictionFn(self):
        if self.plasticStrain:
            friction = self.frictionWeakeningFn(
                self.plasticStrain,
                FrictionCoef=nd(self.frictionCoefficient),
                FrictionCoefSw=nd(self.frictionAfterSoftening),
                epsilon1=self.epsilon1,
                epsilon2=self.epsilon2)
        else:
            friction = fn.misc.constant(nd(self.frictionCoefficient))
        return friction

    def _cohesionFn(self):
        if self.plasticStrain:
            cohesion = self.cohesionWeakeningFn(
                self.plasticStrain,
                Cohesion=nd(self.cohesion),
                CohesionSw=nd(self.cohesionAfterSoftening))
        else:
            cohesion = fn.misc.constant(self.cohesion)
        return cohesion
        
    def _get_yieldStress2D(self):
        f = self._frictionFn()
        C = self._cohesionFn()
        P = self.pressureField
        self.yieldStress = (C * fn.math.cos(f) + P * fn.math.sin(f))
        return self.yieldStress

    def _get_yieldStress3D(self):
        f = self._frictionFn()
        C = self._cohesionFn()
        P = self.pressureField
        self.yieldStress = 6.0*C*fn.math.cos(f) + 2.0*fn.math.sin(f)*fn.misc.max(P, 0.0) 
        self.yieldStress /= (fn.math.sqrt(3.0) * (3.0 + fn.math.sin(f)))
        return self.yieldStress


class VonMises(object):

    def __init__(self, cohesion=None,
                 cohesionAfterSoftening = None,
                 minimumViscosity=None, plasticStrain=None,
                 epsilon1=0.5, epsilon2=1.0):

        self.cohesion = cohesion
        self.cohesionAfterSoftening = cohesionAfterSoftening
        self.minimumViscosity = minimumViscosity
        self.plasticStrain = plasticStrain
        self.pressureField = None
        self.epsilon1 = epsilon1
        self.epsilon2 = epsilon2
        self.cohesionWeakeningFn = linearCohesionWeakening

    @property
    def _cohesion(self):
        if self.plasticStrain:
            cohesion = self.cohesionWeakeningFn(
                self.plasticStrain,
                Cohesion=nd(self.cohesion),
                CohesionSw=nd(self.cohesionAfterSoftening))
        else:
            cohesion = fn.misc.constant(self.cohesion)
        return cohesion
        
    def _get_yieldStress2D(self):
        return self._cohesion

    def _get_yieldStress3D(self):
        return self._cohesion


class ConstantViscosity(Rheology):

    def __init__(self, viscosity):
        super(ConstantViscosity, self).__init__()
        self._viscosity = nd(viscosity)
        self._Quantity = viscosity
        self.name = "Constant ({0})".format(str(viscosity))

    @property
    def muEff(self):
        return self._effectiveViscosity()

    @property
    def Quantity(self):
        return self._Quantity

    @Quantity.setter
    def Quantity(self, value):
        self._Quantity = value

    def _effectiveViscosity(self):
        return fn.misc.constant(nd(self._viscosity))

    def _json_(self):
        return json.dumps(str(self.Quantity))

    def to_json(self):
        if isinstance(self.Quantity, u.Quantity):
            return str(self.Quantity)
        else:
            return self.Quantity

class _ViscousCreepEncoder(JSONEncoder):

    attributes = [
        "name",
        "preExponentialFactor",
        "stressExponent",
        "defaultStrainRateInvariant",
        "activationVolume",
        "activationEnergy",
        "waterFugacity",
        "grainSize",
        "meltFraction",
        "grainSizeExponent",
        "waterFugacityExponent",
        "meltFractionFactor",
        "f",
        "mineral"]

    def default(self, obj):
        d = {}

        for attribute in self.attributes:
            d[attribute] = str(obj[attribute])

        return d
        

class ViscousCreep(Rheology):

    def __init__(self,
                 name=None,
                 strainRateInvariantField=None,
                 temperatureField=None,
                 pressureField=None,
                 preExponentialFactor=1.0,
                 stressExponent=1.0,
                 defaultStrainRateInvariant=1.0e-13 / u.seconds,
                 activationVolume=0.0,
                 activationEnergy=0.0,
                 waterFugacity=None,
                 grainSize=None,
                 meltFraction=None,
                 grainSizeExponent=0.0,
                 waterFugacityExponent=0.0,
                 meltFractionFactor=0.0,
                 f=1.0,
                 mineral="unspecified"):
        
        super(ViscousCreep, self).__init__()
        
        self.name = name
        self.mineral = mineral
        self.strainRateInvariantField = strainRateInvariantField
        self.temperatureField = temperatureField
        self.pressureField = pressureField
        self.preExponentialFactor = preExponentialFactor
        self.stressExponent = stressExponent
        self.defaultStrainRateInvariant = defaultStrainRateInvariant
        self.activationVolume = activationVolume
        self.activationEnergy = activationEnergy
        self.waterFugacity = waterFugacity
        self.grainSize = grainSize
        self.meltFraction = meltFraction
        self.grainSizeExponent = grainSizeExponent
        self.waterFugacityExponent = waterFugacityExponent
        self.meltFractionFactor = meltFractionFactor
        self.f = f
        self.constantGas = 8.3144621 * u.joule / u.mole / u.degK  

    def __mul__(self, other):
        self.f = other
        return self
    
    def __rmul__(self, other):
        self.f = other
        return self

    def __getitem__(self, name):
        return self.__dict__[name]

    def _repr_html_(self):
        attributes  = OrderedDict()
        attributes["Mineral"] = self.mineral
        attributes["Pre-exponential factor"] = self.preExponentialFactor
        attributes["Stress Exponent"] = self.stressExponent
        attributes["Activation Volume"] = self.activationVolume
        attributes["Activation Energy"] = self.activationEnergy
        attributes["Factor"] = self.f
        attributes["Default Strain Rate"] = self.defaultStrainRateInvariant
        attributes["Grain Size"] = self.grainSize
        attributes["Grain Size Exponent"] = self.grainSizeExponent
        attributes["Water Fugacity"] = self.waterFugacity
        attributes["Water Fugacity Exponent"] = self.waterFugacityExponent
        attributes["Melt Fraction"] = self.meltFraction
        attributes["Melt Fraction Factor"] = self.meltFractionFactor
        header = "<table>"
        footer = "</table>"
        html = """
        <tr>
          <th colspan="2">Viscous Creep Rheology: {0}</th>
        </tr>""".format(self.name)
        for key, val in attributes.iteritems():
            if val:
                html += "<tr><td>{0}</td><td>{1}</td></tr>".format(key, val)

        return header + html + footer  

    def _json_(self):
        return json.dumps(self, cls=_ViscousCreepEncoder)

    def to_json(self):
        attributes = [
            "name",
            "preExponentialFactor",
            "stressExponent",
            "defaultStrainRateInvariant",
            "activationVolume",
            "activationEnergy",
            "waterFugacity",
            "grainSize",
            "meltFraction",
            "grainSizeExponent",
            "waterFugacityExponent",
            "meltFractionFactor",
            "f",
            "mineral"]

        d = {}

        for attribute in attributes:
            if isinstance(self[attribute], u.Quantity):
                d[attribute] = str(self[attribute])
            else:
                d[attribute] = self[attribute]

        return d


    @property
    def muEff(self):
        return self._effectiveViscosity()

    def _effectiveViscosity(self):
        """ 
        Return effetive viscosity based on 

        Power law creep equation
        viscosity = 0.5 * A^(-1/n) * edot_ii^((1-n)/n) * d^(m/n) * exp((E + P*V)/(nRT))
        
        A: prefactor
        I: square root of second invariant of deviatoric strain rate tensor,
        d: grain size,
        p: grain size exponent,
        E: activation energy, 
        P: pressure,
        Va; activation volume, 
        n: stress exponent,
        R: gas constant,
        T: temperature.
        """

        A = nd(self.preExponentialFactor)
        n = nd(self.stressExponent)
        P = self.pressureField
        T = self.temperatureField
        Q = nd(self.activationEnergy)
        Va = nd(self.activationVolume)
        p = nd(self.grainSizeExponent)
        d = nd(self.grainSize)
        r = nd(self.waterFugacityExponent)
        fH2O = nd(self.waterFugacity)
        I = self._get_second_invariant()
        f = self.f
        F = nd(self.meltFraction)
        alpha = nd(self.meltFractionFactor)
        R = nd(self.constantGas)

        mu_eff = f * 0.5 * A**(-1.0 / n)

        if np.abs(n - 1.0) > 1e-5:
            mu_eff *= I**((1.0-n)/n)
        
        # Grain size dependency
        if p and d:
            mu_eff *= d**(p/n)

        # Water dependency
        if r and fH2O:
            mu_eff *= fH2O**(-r/n)

        if F:
            mu_eff *= fn.math.exp(-1.0*alpha*F/n)

        if T:
            mu_eff *= fn.math.exp((Q + P * Va) / (R*T*n))

        if self._viscosity_limiter:
            mu_eff = self._viscosity_limiter.apply(mu_eff)
        
        return mu_eff

    def _get_second_invariant(self):
        FirstIterCondition = [(self.firstIter,nd(self.defaultStrainRateInvariant)),
                              (True, self.strainRateInvariantField)]
        return fn.branching.conditional(FirstIterCondition)


class _TemperatureAndDepthDependentViscosityEncoder(JSONEncoder):

    attributes = [
            "eta0",
            "beta",
            "gamma",
            "reference"]

    def default(self, obj):
        d = {}

        for attribute in self.attributes:
            d[attribute] = str(obj[attribute])

        return d


class TemperatureAndDepthDependentViscosity(Rheology):

    def __init__(self, eta0, beta,  gamma, reference, temperatureField=None):
        
        self._eta0 = nd(eta0)
        self._gamma = gamma
        self._beta = gamma
        self._reference = nd(reference)

    @property
    def muEff(self):
        coord = fn.input()
        return self._eta0 * fn.math.exp(gamma * (coord[-1] - reference))
    
    def _json_(self):
        return json.dumps(
            self, cls=_TemperatureAndDepthDependentViscosityEncoder)


class ViscousCreepRegistry(object):
    def __init__(self, filename=None):

        if not filename:
            import pkg_resources
            filename = pkg_resources.resource_filename(__name__, "ressources/ViscousRheologies.json")

        with open(filename, "r") as infile:
            _viscousLaws = json.load(infile)

        for key in _viscousLaws.keys():
            coefficients = _viscousLaws[key]["coefficients"]
            for key2 in coefficients.keys():
                value = coefficients[key2]["value"]
                units = coefficients[key2]["units"]
                if units != "None":
                    coefficients[key2] = u.Quantity(value, units)
                else:
                    coefficients[key2] = value

        self._dir = {}
        for key in _viscousLaws.keys():
            mineral = _viscousLaws[key]["Mineral"]
            name = key.replace(" ","_").replace(",","").replace(".","")
            self._dir[name] = ViscousCreep(name=key, mineral=mineral, **_viscousLaws[key]["coefficients"])


    def __dir__(self):
        # Make all the rheology available through autocompletion
        return list(self._dir.keys())

    def __getattr__(self, item):
        # Make sure to return a new instance of ViscousCreep
        return copy(self._dir[item])


class PlasticityRegistry(object):
    def __init__(self, filename=None):
        
        if not filename:
            import pkg_resources
            filename = pkg_resources.resource_filename(__name__, "ressources/PlasticRheologies.json")

        with open(filename, "r") as infile:
            _plasticLaws = json.load(infile)

        for key in _plasticLaws.keys():
            coefficients = _plasticLaws[key]["coefficients"]
            for key2 in coefficients.keys():
                value = coefficients[key2]["value"]
                units = coefficients[key2]["units"]
                if units != "None":
                    coefficients[key2] = u.Quantity(value, units)
                else:
                    coefficients[key2] = value

        self._dir = {}
        for key in _plasticLaws.keys():
            name = key.replace(" ","_").replace(",","").replace(".","")
            name = name.replace(")","").replace("(","")
            self._dir[name] = DruckerPrager(name=key, **_plasticLaws[key]["coefficients"])

    def __dir__(self):
        # Make all the rheology available through autocompletion
        return list(self._dir.keys())

    def __getattr__(self, item):
        # Make sure to return a new instance of ViscousCreep
        return copy(self._dir[item])