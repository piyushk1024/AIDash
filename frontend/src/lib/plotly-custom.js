import Plotly from 'plotly.js/lib/core'
import bar from 'plotly.js/lib/bar'
import pie from 'plotly.js/lib/pie'
import scatter from 'plotly.js/lib/scatter'
import indicator from 'plotly.js/lib/indicator'
import funnel from 'plotly.js/lib/funnel'
import waterfall from 'plotly.js/lib/waterfall'
import choroplethmapbox from 'plotly.js/lib/choroplethmapbox'
import histogram from 'plotly.js/lib/histogram'
import box from 'plotly.js/lib/box'

Plotly.register([bar, pie, scatter, indicator, funnel, waterfall, choroplethmapbox, histogram, box])

export default Plotly