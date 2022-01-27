
import json
from typing import Dict
import sbol3
import tyto
import paml
from sbol3 import Document

import rdflib as rdfl
from paml_convert.behavior_specialization import BehaviorSpecialization

# FIXME if container ontology is needed, then adapt for use here.
# from container_api.client_api import matching_containers, strateos_id

class OT2Specialization(BehaviorSpecialization):
    def __init__(self,apilevel,leftTipJson,rightTipJson) -> None:
        super().__init__()
        self.var_to_entity = {}
        self.script = ""
        self.scripts = []
        self.all_steps = []
        self.leftTipJson = leftTipJson
        self.rightTipJson = rightTipJson
        self.apilevel = apilevel
        self.protocol = None
        self.step = 0
        self.sequence = []
        self.sequenceDict = {}
        self.header = ""
        self.type = "OT2Specialization"
        self.container = ""
        # Needed for using container ontology
        self.container_api_addl_conditions = "(cont:availableAt value <https://sift.net/container-ontology/strateos-catalog#Strateos>)"

    def _init_behavior_func_map(self) -> dict:
        """
        This function redirects processing of each primitive to the functions
        defined below.  Adding additional mappings here is most likely required.
        """
        return {
            "https://bioprotocols.org/paml/primitives/sample_arrays/EmptyContainer" : self.define_container,
            "https://bioprotocols.org/paml/primitives/liquid_handling/Provision" : self.provision_container,
            "https://bioprotocols.org/paml/primitives/liquid_handling/TransferInto" : self.transfer_into,
            "https://bioprotocols.org/paml/primitives/sample_arrays/PlateCoordinates" : self.plate_coordinates,
            "https://bioprotocols.org/paml/primitives/spectrophotometry/MeasureAbsorbance" : self.not_implemented,
        }

    def on_begin(self):
        protocol = self.execution.protocol.lookup()
        apilevel = self.apilevel
        self.header += f"#Protocol Name:{protocol.name}\n\n\n"
        self.header += "from opentrons import protocol_api\n\n"
        self.header += "metadata = {'apiLevel': '"+apilevel+"'}\n\n"
        self.header += self._tipracks(json.loads(self.leftTipJson),json.loads(self.rightTipJson))
        self.header += self._materials(protocol)
        self.header += "#END OF HEADER\n\n"
   
    def on_end(self):
        self.script += self.header
        self.script += self._steps()
        

    def _steps(self):
        markdown = '\n#Steps\n'
        for i, step in enumerate(self.all_steps):
           markdown += step + '\n'
        return markdown
        
    def _tipracks(self, left,right):
        leftTipID = left["pipette"]
        rightTipID = right["pipette"]
        tipCount=0
        tipList=""
        markdown=""
        for tiprack in left["tipracks"]:
            tiprackID = tiprack["id"]
            tiprackDeck = tiprack["deck"]
            tipList += f"leftTiprack{tipCount},"
            markdown += f"leftTiprack{tipCount} = protocol.load_labware('{tiprackID}', {tiprackDeck})\n"
            tipCount+=1
        markdown += f"left = protocol.load_instrument('{leftTipID}', 'left', tip_rack={tipList[:-1]})\n"
        tipCount=0
        tipList=""
        for tiprack in right["tipracks"]:
            tiprackID = tiprack["id"]
            tiprackDeck = tiprack["deck"]
            tipList += f"rightTiprack{tipCount},"
            markdown += f"rightTiprack{tipCount} = protocol.load_labware('{tiprackID}', {tiprackDeck})\n"
            tipCount+=1
        markdown += f"right = protocol.load_instrument('{rightTipID}', 'right', tip_rack={tipList[:-1]})\n"
        return markdown
        
    def _materials(self, protocol):
        document_objects = protocol.document.objects
        components = [x for x in protocol.document.objects if isinstance(x, sbol3.component.Component)]
        materials = {x.display_id: x for x in components}
        markdown = '\n\n#Protocol Materials\n'
        labware = set()
        for name, material  in materials.items():
             OT2Props = json.loads(material.OT2SpecificProps)
             source = OT2Props["source"]
             if source in labware:
                markdown += f"#[{name}]({material.types[0]})\n"
             else:
                type = OT2Props["type"]
                deck = OT2Props["deck"]
                markdown += f"#[{name}]({material.types[0]})\n"
                markdown += f"{source} = protocol.load_labware('{type}', {deck})\n"
                labware.add(OT2Props["source"])
            
        return markdown
        
    def _parameter_value_markdown(self, pv : paml.ParameterValue, is_output=False):
        parameter = pv.parameter.lookup().property_value
        value = pv.value.lookup().value if isinstance(pv.value, uml.LiteralReference) else pv.value.value
        units = tyto.OM.get_term_by_uri(value.unit) if isinstance(value, sbol3.om_unit.Measure) else None
        value = str(f"{value.value} {units}")  if units else str(value)
        if is_output:
            return f"* `{parameter.name}`"
        else:
            return f"* `{parameter.name}` = {value}"

    def _resolveToUnit(self,uri):
        if 'http://www.ontology-of-units-of-measure.org' in uri:
            return tyto.OM.get_term_by_uri(uri)
        else:
            return uri
    
    
    def define_container(self, record: paml.ActivityNodeExecution):
        protocol = self.execution.protocol.lookup()
        call = record.call.lookup()
        parameter_value_map = call.parameter_value_map()

        spec = parameter_value_map["specification"]['value']
        samples_var = parameter_value_map["samples"]['value']

        # FIXME the protocol var_to_entity mapping links variables created in
        # the execution trace with real values assigned here, such as
        # container below.  This mapping can be used in later processing to
        # reuse bindings.
        #
        # self.var_to_entity[samples_var] = container
        OT2Props = json.loads(spec.OT2SpecificProps)
        OT2Deck = OT2Props["deck"]
        self.var_to_entity[samples_var.get_parent().get_parent().display_id]=spec.name
        self.container += f"{spec.name} = protocol.load_labware('{spec.queryString}', {OT2Deck})\n"
        self.sequenceDict[
            call.identity
        ] = f"{spec.name} = protocol.load_labware('{spec.queryString}', {OT2Deck})\n"
        self.sequence += [call.identity]
        


    def provision_container(self, record: paml.ActivityNodeExecution):
        results = {}
        call = record.call.lookup()
        parameter_value_map = call.parameter_value_map()
        destination = parameter_value_map["destination"]["value"]
        value = parameter_value_map["amount"]["value"].value
        units = parameter_value_map["amount"]["value"].unit
        units = tyto.OM.get_term_by_uri(units)
        resource = parameter_value_map["resource"]["value"]
        OT2Props = json.loads(resource.OT2SpecificProps)
        OT2Source = OT2Props["source"]
        OT2Pipette="left"
        try:
           OT2Coordinates=OT2Props["coordinates"]
        except:
           OT2Coordinates="A1"
        try:
            if velocityUnit=="Milliliter per Second":
                velocity = parameter_value_map["dispenseVelocity"]["value"].value*1000
            else:
                self.all_steps += [f"#  Unsupported Unit {velocityUnit} for attribute dispenseVelocity"]
                raise AttributeError("Unsupported Unit for attribute dispenseVelocity")
        except:
            velocity = 150
        destPlate=self.var_to_entity[destination.source.lookup().value.lookup().get_parent().display_id]
        destination_str = f"{destination.mask}"
        self.all_steps += [f"transfer(protocol,{OT2Pipette},{value},{OT2Source},'{OT2Coordinates}',{destPlate},'{destination_str}',{velocity},0)"]
        self.sequenceDict[
            call.identity
        ] = f"transfer(protocol,{OT2Pipette},{value},{OT2Source},'{OT2Coordinates}',{destPlate},'{destination_str}',{velocity},0)"
        self.sequence += [call.identity]

        
    def transfer_into(self, record: paml.ActivityNodeExecution):
        results = {}
        call = record.call.lookup()
        parameter_value_map = call.parameter_value_map()
        destination = parameter_value_map["destination"]["value"]
        source = parameter_value_map["source"]["value"]
        amount = parameter_value_map["amount"]["value"].value
        amountUnit = parameter_value_map["amount"]["value"].unit
        velocityUnit = parameter_value_map["dispenseVelocity"]["value"].unit
        mixCycles = parameter_value_map["mixCycles"]["value"].value
        mixCyclesUnit = parameter_value_map["mixCycles"]["value"].unit
        amountUnit = self._resolveToUnit(amountUnit)
        velocityUnit = self._resolveToUnit(velocityUnit)
        mixCyclesUnit = self._resolveToUnit(mixCyclesUnit)
        try:
            if velocityUnit=="Milliliter per Second":
                velocity = parameter_value_map["dispenseVelocity"]["value"].value*1000
            else:
                self.all_steps += [f"#  Unsupported Unit {velocityUnit} for attribute dispenseVelocity"]
                raise AttributeError("Unsupported Unit for attribute dispenseVelocity")
        except:
            velocity = 150
            
        try:
            if mixCyclesUnit=="Count":
                mixCycles = parameter_value_map["mixCycles"]["value"].value
            else:
                self.all_steps += [f"#  Unsupported Unit {mixCyclesUnit} for attribute mixCycles"]
                raise AttributeError("Unsupported Unit")
        except:
            mixCycles = 0

        #units = tyto.OM.get_term_by_uri(units)
        sourcePlate=self.var_to_entity[source.source.lookup().value.lookup().get_parent().display_id]
        destPlate=self.var_to_entity[destination.source.lookup().value.lookup().get_parent().display_id]
        OT2Pipette="left"
        source_str = f"{source.mask}"
        destination_str = f"{destination.mask}"
        self.sequenceDict[
            call.identity
        ] = f"transfer(protocol,{OT2Pipette},{amount},{sourcePlate},'{source_str}',{destPlate},'{destination_str}',{velocity},{mixCycles})"
        self.sequence += [call.identity]
        self.all_steps += [
            f"transfer(protocol,{OT2Pipette},{amount},{sourcePlate},'{source_str}',{destPlate},'{destination_str}',{velocity},{mixCycles})"
        ]
        
    def plate_coordinates(self, record: paml.ActivityNodeExecution):
        call = record.call.lookup()
        parameter_value_map = call.parameter_value_map()
        source = parameter_value_map["source"]["value"]
        coords = parameter_value_map["coordinates"]["value"]
        
    def not_implemented(self, record: paml.ActivityNodeExecution):
        protocol = self.execution.protocol.lookup()
        apilevel = self.apilevel
