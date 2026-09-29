from .wps_cf_check import CFCheck
from .wps_plot_climate_stripes import PlotClimateStripes
from .wps_plot_climate_stripes_global import PlotClimateStripesGlobal

processes = [
    CFCheck(),
    PlotClimateStripes(),
    PlotClimateStripesGlobal(),
]
