import os
import shutil
from collections import namedtuple

from pywps import (
    BoundingBoxInput,
    LiteralInput,
    Process,
    FORMATS,
    Format,
    ComplexOutput,
)
from pywps.inout.formats import _FORMATS  # noqa

from pywps.app.Common import Metadata
from pywps.app.exceptions import ProcessError

from vulture.utils import get_input
from vulture.stripes_lib.stripes import StripesRenderer
from vulture.mock_data import pause  # MOCK: simulated processing time


import logging
LOGGER = logging.getLogger("PYWPS")


# Extend FORMATS
def get_extended_pywps_FORMATS():
    """
    Returns a FORMATS object, with additional formats:
    - PDF
    - PNG
    """
    new_formats = [
        ("PDF", Format('application/pdf', extension='.pdf')),
        ("PNG", Format('image/png', extension='.png'))]

    FORMATS_EXT = namedtuple('FORMATS_EXT', _FORMATS._fields + \
                             tuple(fmt[0] for fmt in new_formats))
    all_formats = [fmt_spec for _, fmt_spec in FORMATS._asdict().items()] + \
                  [fmt[1] for fmt in new_formats]

    return FORMATS_EXT(*all_formats)


FORMATS_EXT = get_extended_pywps_FORMATS()


_abstract = (
"Plot your own climate stripes figure! Choose a start and end year and a location within "
"the UK and we'll use this to make a personalised climate stripes image for your area. " 
"""
All we need is the latitude and longitude of your location, you can find this information at https://www.latlong.net . 
""" 
"The programme will take a little while to run after submission. Once it has completed click "
"'Show Output' to view a pdf with your figure! The pdf has a table showing the breakdown of each "
"year, the temperature for that year and the corresponding colour. It will also show you how many "
"times each colour is used in the figure."
"""
You can find out more about climate stripes and discover inspiration for things to do with them here: 
https://www.ceda.ac.uk/outreach 
"""
)


class PlotClimateStripes(Process):

    IDENTIFIER = "PlotClimateStripes"
    TITLE = "Plot Climate Stripes"
    ABSTRACT = _abstract #"Plots Climate Stripes...ad more text"
    KEYWORDS = ["climate", "observations", "change"]
    INPUTS_LIST = ["latitude", "longitude"]
    METALINK_ID = "plot-climate-stripes-result"

    PROCESS_METADATA = [
        Metadata("CEDA WPS UI", "https://ceda-wps-ui.ceda.ac.uk"),
        Metadata("CEDA WPS", "https://ceda-wps.ceda.ac.uk"),
        Metadata("Disclaimer", "https://help.ceda.ac.uk/article/4642-disclaimer"),
        Metadata("https://www.latlong.net", "https://www.latlong.net"),
        Metadata("https://www.ceda.ac.uk/outreach", "https://www.ceda.ac.uk/outreach")
    ]

    def __init__(self):

        inputs = self._define_inputs()
        outputs = self._define_outputs()

        super(PlotClimateStripes, self).__init__(
            self._handler,
            identifier=self.IDENTIFIER,
            title=self.TITLE,
            abstract=self.ABSTRACT,
            keywords=self.KEYWORDS,
            metadata=self.PROCESS_METADATA,
            version="1.0.0",
            inputs=inputs,
            outputs=outputs,
            store_supported=True,
            status_supported=True,
        )

    def _define_input(self, name, long_name, abstract, dtype="string", allowed_values=None, optional=False, default=None):
        return LiteralInput(
            name,
            long_name,
            abstract=abstract,
            data_type=dtype,
            allowed_values=allowed_values,
            min_occurs=(0 if optional else 1),
            max_occurs=1,
            default=default
        )

    def _define_inputs(self):
        inputs = [
            self._define_input("project_name", "Project name", "Enter a name for your project", "string", optional=True),
            self._define_input("latitude", "Latitude", 
                               "Latitude is how far the location is from the equator, most of the UK is between 50 and 59 degrees North.",
                               "float"),
            self._define_input("longitude", "Longitude", 
                               ("Longitude is how far the place is from the Prime Meridian which goes vertically through Greenwich in London. "
                                "Anything East of this will be a positive number whilst anything West will be a negative number."), 
                               "float"),
            self._define_input("n_colours", "Number of Colours", 
                               ("Enter the number of colours you’d like in your figure. The minimum is 5 and the maximum is 100, "
                                "we recommend 20 colours."), "integer", default=20),
            self._define_input("start_year", "Start year", 
                               "Enter the year you would like the data to start from. Note: most of the data starts in 1901.", 
                               "integer", default=1901),
            self._define_input("end_year", "End year", 
                               "Enter the year you would like the data to finish on. The last available year is 2022.", 
                               "integer", default=2000)
            
#        LiteralInput( "yearNumericRange", "Time Period", abstract="The time period", data_type="string", default="1901/2000", min_occurs=1, max_occurs=1,)

        ] 
        return inputs

    def _define_outputs(self):
        outputs = [
            ComplexOutput('output', 'Output',
                          abstract='Output file',
                          as_reference=True,
                          supported_formats=[FORMATS_EXT.PDF]),
            ComplexOutput('png_output', 'PNG Output',
                          as_reference=True,
                          supported_formats=[FORMATS_EXT.PNG])
            ]
        return outputs


    def _handler(self, request, response):

        lat = get_input(request.inputs, "latitude")
        lon = get_input(request.inputs, "longitude")
        project_name = get_input(request.inputs, "project_name")
        n_colours = get_input(request.inputs, "n_colours")
        start_year = get_input(request.inputs, "start_year")
        end_year = get_input(request.inputs, "end_year")
    #    time_range = get_input(request.inputs, "yearNumericRange") 
   #     inputs = {"latitude": lat, "longitude": lon, "project_name": project_name}
   #     except Exception as exc:
   #        raise ProcessError(f"An error occurred when converting to CSV: {str(exc)}")

        png_file = os.path.join(self.workdir, "stripes.png")
        pdf_file = os.path.join(self.workdir, "stripes.pdf")
#        shutil.copy("/tmp/climate-stripes.png", output_file)

        # Make the stripes
        stripes_maker = StripesRenderer()
        response.update_status('Begin data loading', 10)
        pause()

#        RAL = [51.570664384, -1.308832098]
        df = stripes_maker.create(lat, lon, n_colours=n_colours, output_file=png_file, time_range=(start_year, end_year))

        response.update_status('Data extracted', 70)
        pause()

#        html = stripes_maker.to_html(html_file="/tmp/output.html", project_name="My great project")
        pdf_file_ = stripes_maker.to_pdf(pdf_file, project_name=project_name)
                
        response.update_status('Outputs written', 90)

        LOGGER.info(f'Written output file: {pdf_file}')
        response.outputs['output'].file = pdf_file
        response.outputs['png_output'].file = png_file
        return response


