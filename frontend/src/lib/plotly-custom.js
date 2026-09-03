import Plotly from 'plotly.js/lib/core'
import bar from 'plotly.js/lib/bar'
import pie from 'plotly.js/lib/pie'
import scatter from 'plotly.js/lib/scatter'
import indicator from 'plotly.js/lib/indicator'
import funnel from 'plotly.js/lib/funnel'
import sankey from 'plotly.js/lib/sankey'
import histogram from 'plotly.js/lib/histogram'
import box from 'plotly.js/lib/box'
import table from 'plotly.js/lib/table'
import heatmap from 'plotly.js/lib/heatmap'
import scattermap from 'plotly.js/lib/scattermap'

Plotly.register([bar, pie, scatter, indicator, funnel, sankey, histogram, box, table, heatmap, scattermap])

export default Plotly