// 只注册用到的图表与组件，让打包工具能去掉 ECharts 的其余部分。
// 本模块只会被动态引入（见 star-chart.ts），首屏不加载。
import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { init, use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

use([BarChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

export { init };
