import os
import tempfile
import sbol3
import paml
import tyto
import uml
import json
import rdflib as rdfl
from typing import Dict


from paml.execution_engine import ExecutionEngine
from paml_check.paml_check import check_doc
from paml_convert.ot2.ot2_specialization import OT2Specialization
from paml_convert.markdown.markdown_specialization import MarkdownSpecialization

# Dev Note: This is a test of the initial version of the OT2 specialization. Any specs shown here can be changed in the future. Use at your own risk. Here be dragons.


#############################################
# set up the document
print("Setting up document")
doc = sbol3.Document()
sbol3.set_namespace("https://bbn.com/scratch/")

#############################################
# Import the primitive libraries
print("Importing libraries")
paml.import_library("liquid_handling")
print("... Imported liquid handling")
paml.import_library("plate_handling")
print("... Imported plate handling")
paml.import_library("spectrophotometry")
print("... Imported spectrophotometry")
paml.import_library("sample_arrays")
print("... Imported sample arrays")

# Example of how to generate a template for a new protocol step

# print(primitives["https://bioprotocols.org/paml/primitives/liquid_handling/Dispense"].template())

protocol = paml.Protocol("iGEM_LUDOX_OD_calibration_2018")
protocol.name = "iGEM 2018 LUDOX OD calibration protocol"
protocol.description = """
Test Execution
"""
doc.add(protocol)

wavelength_param = protocol.input_value(
    "wavelength",
    sbol3.OM_MEASURE,
    optional=True,
    default_value=sbol3.Measure(600, tyto.OM.nanometer),
)

# create the materials to be provisioned
CONT_NS = rdfl.Namespace("https://sift.net/container-ontology/container-ontology#")
OM_NS = rdfl.Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")
PREFIX_MAP = json.dumps({"cont": CONT_NS, "om": OM_NS})
ul_per_s = sbol3.UnitDivision(
    "microliter_per_second",
    "uL/s",
    "microliter_per_second",
    tyto.OM.microliter,
    tyto.OM.second,
)


ddh2o = sbol3.Component("ddH2O", "https://identifiers.org/pubchem.substance:24901740")
ddh2o.name = "Water, sterile-filtered, BioReagent, suitable for cell culture"
ddh2o.OT2SpecificProps = sbol3.TextProperty(ddh2o, "", 0, 1)
# indicate where ddh2o is loaded, use JSON to set OT2 Specific parameters; might be cleaner and more pythonesque using a dictionary but this should do for now
# water is in well A1 of reservoir. since no coordinates were issued its assumed to be loaded into well A1
ddh2o.OT2SpecificProps = (
    '{"deck":"1", "source":"reservoir", "type":"nest_12_reservoir_15ml"}'
)
doc.add(ddh2o)

ludox = sbol3.Component("LUDOX", "https://identifiers.org/pubchem.substance:24866361")
ludox.name = "LUDOX(R) CL-X colloidal silica, 45 wt. % suspension in H2O"
ludox.OT2SpecificProps = sbol3.TextProperty(ludox, "", 0, 1)
# indicate where ludox is loaded, use JSON to set OT2 Specific parameters; might be cleaner and more pythonesque using a dictionary but this should do for now
# ludox is in well A2 of reservoir, no need to redeclare source type as long as it was declared before
ludox.OT2SpecificProps = '{"coordinates":"A2", "source":"reservoir"}'
doc.add(ludox)

# actual steps of the protocol
# get a plate
platespec1 = paml.ContainerSpec(
    queryString="corning_48_wellplate_1.6ml_flat", prefixMap=PREFIX_MAP, name="plate1"
)
platespec1.OT2SpecificProps = sbol3.TextProperty(
    platespec1,
    "https://bioprotocols.org/paml/primitives/sample_arrays/EmptyContainer/OT2/Deck",
    0,
    1,
)
platespec1.OT2SpecificProps = '{"deck":"2"}'
plate1 = protocol.primitive_step(
    "EmptyContainer", specification=platespec1
)  # declare a plate loaded in the second deck

platespec2 = paml.ContainerSpec(
    queryString="corning_48_wellplate_1.6ml_flat", prefixMap=PREFIX_MAP, name="plate2"
)
platespec2.OT2SpecificProps = sbol3.TextProperty(
    platespec2,
    "https://bioprotocols.org/paml/primitives/sample_arrays/EmptyContainer/OT2/Deck",
    0,
    1,
)
platespec2.OT2SpecificProps = '{"deck":"3"}'
plate2 = protocol.primitive_step(
    "EmptyContainer", specification=platespec2
)  # declare a plate loaded in the third deck

# identify wells to use
c_ddh2o = protocol.primitive_step(
    "PlateCoordinates", source=plate1.output_pin("samples"), coordinates="A1:D1"
)
# put water in selected wells
provision_ddh2o = protocol.primitive_step(
    "Provision",
    resource=ddh2o,
    destination=c_ddh2o.output_pin("samples"),
    amount=sbol3.Measure(100, tyto.OM.microliter),
)
# identify wells to use
c_ludox = protocol.primitive_step(
    "PlateCoordinates", source=plate1.output_pin("samples"), coordinates="A2:D2"
)
# put ludox in selected wells
provision_ludox = protocol.primitive_step(
    "Provision",
    resource=ludox,
    destination=c_ludox.output_pin("samples"),
    amount=sbol3.Measure(100, tyto.OM.microliter),
)
c_measure1 = protocol.primitive_step(
    "PlateCoordinates", source=plate1.output_pin("samples"), coordinates="A1:D2"
)
c_absorbance1 = protocol.primitive_step(
    "MeasureAbsorbance",
    samples=c_measure1.output_pin("samples"),
    wavelength=wavelength_param,
)
output1 = protocol.designate_output(
    "absorbance", sbol3.OM_MEASURE, c_absorbance1.output_pin("measurements")
)

# identify wells to use
c_ddh2o2 = protocol.primitive_step(
    "PlateCoordinates", source=plate2.output_pin("samples"), coordinates="A1:D1"
)
# put water in selected wells
provision_ddh2o2 = protocol.primitive_step(
    "Provision",
    resource=ddh2o,
    destination=c_ddh2o2.output_pin("samples"),
    amount=sbol3.Measure(100, tyto.OM.microliter),
)
# identify wells to use
c_ludox2 = protocol.primitive_step(
    "PlateCoordinates", source=plate2.output_pin("samples"), coordinates="A2:D2"
)
# put ludox in selected wells
provision_ludox2 = protocol.primitive_step(
    "Provision",
    resource=ludox,
    destination=c_ludox2.output_pin("samples"),
    amount=sbol3.Measure(100, tyto.OM.microliter),
)

c_measure2 = protocol.primitive_step(
    "PlateCoordinates", source=plate2.output_pin("samples"), coordinates="A1:D2"
)
c_absorbance2 = protocol.primitive_step(
    "MeasureAbsorbance",
    samples=c_measure2.output_pin("samples"),
    wavelength=wavelength_param,
)
output2 = protocol.designate_output(
    "absorbance", sbol3.OM_MEASURE, c_absorbance2.output_pin("measurements")
)

protocol.order(protocol.get_last_step(), output2)
# Begin Execution
output = None
parameter_values = [
    paml.ParameterValue(
        parameter=protocol.get_input("wavelength"),
        value=sbol3.Measure(100, tyto.OM.nanometer),
    )
]
OT2agent = sbol3.Agent("OT2_agent")
leftTiprackSettingJSON = '{"pipette":"p1000_single_gen2","tipracks":[{"id":"geb_96_tiprack_1000ul","deck":4},{"id":"geb_96_tiprack_1000ul","deck":5}]}'
rightTiprackSettingJSON = '{"pipette":"p20_single_gen2","tipracks":[{"id":"opentrons_96_tiprack_20ul","deck":6},{"id":"opentrons_96_tiprack_20ul","deck":7}]}'
OT2ee = ExecutionEngine(
    specializations=[
        OT2Specialization("2.11", leftTiprackSettingJSON, rightTiprackSettingJSON),
        MarkdownSpecialization("/dev/null"),
    ]
)
OT2execution = OT2ee.execute(
    protocol, OT2agent, id="OT2_execution", parameter_values=parameter_values
)

# Multi Execution Logic Here - Put in Separate class later


specializations = OT2ee.specializations
exeList = OT2ee.specializations[len(specializations) - 1].sequence.copy()
thisScript = specializations[0].header
finalScript = []
scriptCount = 1
finalMarkdown = []


for i in range(len(exeList)):
    for j in range(len(specializations)-1):

        if exeList[i] in specializations[j].sequence and specializations[len(specializations)-1].sequenceDict[exeList[i]] != "":
            specializations[len(specializations)-1].sequenceDict[exeList[i]] = f"Run script_{scriptCount}.py"

        if specializations[j].type == "OT2Specialization" and exeList[i] not in specializations[j].sequence:
            scriptCount += 1
            finalScript+=[thisScript]
            thisScript = f"#Script No. {scriptCount}"
            thisScript += specializations[0].header

        if specializations[j].type == "OT2Specialization" and exeList[i] in specializations[j].sequence:
            thisScript += specializations[j].sequenceDict[exeList[i]]+"\n"

previous=""
for i in exeList:
	entry = specializations[len(specializations)-1].sequenceDict[i]
	if previous != entry:
		finalMarkdown += [f"{specializations[len(specializations)-1].sequenceDict[i]}"]
		previous = entry

outputMarkdown= specializations[len(specializations)-1].header
for i in range(len(finalMarkdown)):
		outputMarkdown += f"\n{i+1}. {finalMarkdown[i]}"

try:
    os.mkdir(protocol.display_id)
except:
	print("")
for i in range(len(finalScript)):
         with open(f"{protocol.display_id}/script_{i+1}.py", "w") as f:
            f.write(finalScript[i])
with open(f"{protocol.display_id}/README.md", "w") as f:
         f.write(outputMarkdown)

# End Multiexecution Logic

# v = doc.validate()
# assert len(v) == 0, "".join(f'\n {e}' for e in v)

# temp_name = os.path.join(tempfile.gettempdir(), 'ludox.nt')
# doc.write(temp_name, sbol3.SORTED_NTRIPLES)
# print(f'Wrote file as {temp_name}')

# render and view the dot
# dot = protocol.to_dot()
# dot.render(f'{protocol.name}.gv')
# dot.view()
