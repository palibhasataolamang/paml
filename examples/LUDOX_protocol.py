import json
import logging
import os
from typing import Tuple
import copy
import rdflib as rdfl
import sbol3
import tyto
from sbol3 import Document
import paml
from paml.execution_engine import ExecutionEngine
from paml_check.paml_check import check_doc
from paml_convert.ot2.ot2_specialization import OT2Specialization
from paml_convert.markdown.markdown_specialization import MarkdownSpecialization


CONT_NS = rdfl.Namespace("https://sift.net/container-ontology/container-ontology#")
OM_NS = rdfl.Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")


def prepare_document() -> Document:

    doc = sbol3.Document()
    sbol3.set_namespace("https://bci.ph/SynBio")
    return doc


def import_paml_libraries() -> None:
    paml.import_library("liquid_handling")
    paml.import_library("plate_handling")
    paml.import_library("spectrophotometry")
    paml.import_library("sample_arrays")


DOCSTRING = """
With this protocol you will use LUDOX CL-X (a 45% colloidal silica suspension) as a single point reference to
obtain a conversion factor to transform absorbance (OD600) data from your plate reader into a comparable
OD600 measurement as would be obtained in a spectrophotometer. This conversion is necessary because plate
reader measurements of absorbance are volume dependent; the depth of the fluid in the well defines the path
length of the light passing through the sample, which can vary slightly from well to well. In a standard
spectrophotometer, the path length is fixed and is defined by the width of the cuvette, which is constant.
Therefore this conversion calculation can transform OD600 measurements from a plate reader (i.e. absorbance
at 600 nm, the basic output of most instruments) into comparable OD600 measurements. The LUDOX solution
is only weakly scattering and so will give a low absorbance value.
        """


def create_protocol() -> paml.Protocol:
    protocol: paml.Protocol = paml.Protocol("iGEM_LUDOX_OD_calibration_2018")
    protocol.name = "iGEM 2018 LUDOX OD calibration protocol"
    protocol.description = DOCSTRING
    return protocol


def create_h2o() -> sbol3.Component:
    ddh2o = sbol3.Component(
        "ddH2O", "https://identifiers.org/pubchem.substance:24901740"
    )
    ddh2o.name = "Water, sterile-filtered, BioReagent, suitable for cell culture"
    ddh2o.OT2SpecificProps = sbol3.TextProperty(
        ddh2o,
        "https://bioprotocols.org/paml/primitives/sample_arrays/EmptyContainer/OT2/Deck",
        0,
        1,
    )
    ddh2o.OT2SpecificProps = (
        '{"deck":"1", "source":"reservoir", "type":"nest_12_reservoir_15ml"}'
    )
    return ddh2o


def create_ludox() -> sbol3.Component:
    ludox = sbol3.Component(
        "LUDOX", "https://identifiers.org/pubchem.substance:24866361"
    )
    ludox.name = "LUDOX(R) CL-X colloidal silica, 45 wt. % suspension in H2O"
    ludox.OT2SpecificProps = sbol3.TextProperty(
        ludox,
        "https://bioprotocols.org/paml/primitives/sample_arrays/EmptyContainer/OT2/Deck",
        0,
        1,
    )
    ludox.OT2SpecificProps = '{"coordinates":"A2", "source":"reservoir"}'
    return ludox


PLATE_SPECIFICATION = """cont:ClearPlate and 
 cont:SLAS-4-2004 and
 (cont:wellVolume some 
    ((om:hasUnit value om:microlitre) and
     (om:hasNumericalValue only xsd:decimal[>= "200"^^xsd:decimal])))"""

PREFIX_MAP = json.dumps({"cont": CONT_NS, "om": OM_NS})


def create_plate(protocol: paml.Protocol):
    # graph: rdfl.Graph = protocol._other_rdf
    # plate_spec_uri = \
    #     "https://bbn.com/scratch/iGEM_LUDOX_OD_calibration_2018/container_requirement#RequiredPlate"
    # graph.add((plate_spec_uri, CONT_NS.containerOntologyQuery, PLATE_SPECIFICATION))
    # plate_spec = sbol3.Identified(plate_spec_uri,
    #                               "foo", name="RequiredPlate")
    spec = paml.ContainerSpec(
        queryString="corning_48_wellplate_1.6ml_flat",
        prefixMap=PREFIX_MAP,
        name="plateRequirement",
    )
    spec.OT2SpecificProps = sbol3.TextProperty(
        spec,
        "https://bioprotocols.org/paml/primitives/sample_arrays/EmptyContainer/OT2/Deck",
        0,
        1,
    )
    spec.OT2SpecificProps = '{"deck":"2"}'
    plate = protocol.primitive_step("EmptyContainer", specification=spec)
    plate.name = "calibration plate"
    return plate


def provision_h2o(protocol: paml.Protocol, plate, ddh2o) -> None:
    c_ddh2o = protocol.primitive_step(
        "PlateCoordinates", source=plate.output_pin("samples"), coordinates="A1:D1"
    )
    protocol.primitive_step(
        "Provision",
        resource=ddh2o,
        destination=c_ddh2o.output_pin("samples"),
        amount=sbol3.Measure(100, tyto.OM.microliter),
    )


def provision_ludox(protocol: paml.Protocol, plate, ludox) -> None:
    c_ludox = protocol.primitive_step(
        "PlateCoordinates", source=plate.output_pin("samples"), coordinates="A2:D2"
    )
    protocol.primitive_step(
        "Provision",
        resource=ludox,
        destination=c_ludox.output_pin("samples"),
        amount=sbol3.Measure(100, tyto.OM.microliter),
    )


def measure_absorbance(protocol: paml.Protocol, plate, wavelength_param):
    c_measure = protocol.primitive_step(
        "PlateCoordinates", source=plate.output_pin("samples"), coordinates="A1:D2"
    )
    return protocol.primitive_step(
        "MeasureAbsorbance",
        samples=c_measure.output_pin("samples"),
        wavelength=wavelength_param,
    )


def ludox_protocol() -> Tuple[paml.Protocol, Document]:
    #############################################
    # set up the document
    doc: Document = prepare_document()

    #############################################
    # Import the primitive libraries
    import_paml_libraries()

    #############################################
    # Create the protocol
    protocol: paml.Protocol = create_protocol()
    doc.add(protocol)

    # create the materials to be provisioned
    ddh2o = create_h2o()
    doc.add(ddh2o)

    ludox = create_ludox()
    doc.add(ludox)

    # add an optional parameter for specifying the wavelength
    wavelength_param = protocol.input_value(
        "wavelength",
        sbol3.OM_MEASURE,
        optional=True,
        default_value=sbol3.Measure(600, tyto.OM.nanometer),
    )

    # actual steps of the protocol
    # get a plate
    plate = create_plate(protocol)

    # put ludox and water in selected wells
    provision_h2o(protocol, plate, ddh2o)
    provision_ludox(protocol, plate, ludox)

    # measure the absorbance
    measure = measure_absorbance(protocol, plate, wavelength_param)
    output = protocol.designate_output(
        "absorbance", sbol3.OM_MEASURE, measure.output_pin("measurements")
    )
    protocol.order(protocol.get_last_step(), output)

    return protocol, doc


if __name__ == "__main__":
    new_protocol: paml.Protocol
    new_protocol, doc = ludox_protocol()
    output = None
    parameter_values = [
        paml.ParameterValue(
            parameter=new_protocol.get_input("wavelength"),
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
        new_protocol, OT2agent, id="OT2_execution", parameter_values=parameter_values
    )
    print(OT2ee.specializations[0].script)
    print(OT2ee.specializations[0].script_sequence)

    # protocol_object=None
    # for object in doc2.objects:
    #   if(object.type_uri=="http://bioprotocols.org/paml#Protocol"):
    #       protocol_object=object
    #       doc2.change_object_namespace([object],"https://bci.ph/SynBio/multiexec2")
    # parameter_values2 = [paml.ParameterValue(parameter=protocol_object.get_input("wavelength"),value=sbol3.Measure(100, tyto.OM.nanometer))]
    # MDagent = sbol3.Agent("MD_agent")
    # MDee = ExecutionEngine(specializations=[MarkdownSpecialization("test_LUDOX_markdown.md")])
    # MDexecution = MDee.execute(protocol_object, MDagent, id="MD_execution",parameter_values=parameter_values2)
    # print(MDee.specializations[0].markdown)

    print("Validating and writing protocol")
    v = doc.validate()
    assert len(v) == 0, "".join(f"\n {e}" for e in v)

    rdf_filename = os.path.join(
        os.path.dirname(__file__), "iGEM 2018 LUDOX OD calibration protocol.nt"
    )
    doc.write(rdf_filename, sbol3.SORTED_NTRIPLES)
    print(f"Wrote temp file as {rdf_filename}")

    # rdf_filename = os.path.join(os.path.dirname(__file__), 'iGEM 2018 LUDOX OD calibration protocol1.nt')
    # doc2.write(rdf_filename, sbol3.SORTED_NTRIPLES)
    # print(f'Wrote temp file as {rdf_filename}')

    # render and view the dot
    # dot = new_protocol.to_dot()
    # dot.render(f'{new_protocol.name}.gv')
    # dot.view()
