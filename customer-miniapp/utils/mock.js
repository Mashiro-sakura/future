export const mockOverview = {
  latest_report: {
    id: 1,
    report_date: '2026-07-09',
    session_name: 'evening',
    title: '2026-07-09 PTA/PVC/塑料期现晚报',
    market_summary:
      'PTA：主力合约TA2609，期货5862，现货5910，基差48，建议小单补库。\nPVC：主力合约V2609，期货5620，现货5580，基差-40，建议逢低采购。\nLLDPE：主力合约L2609，期货8190，现货8250，基差60，建议观望等待。\nPP：主力合约PP2609，期货7442，现货7380，基差-62，建议积极采购。\nOCT：现货8200，暂不做期货盘面分析，建议观望等待。',
    price_behavior_analysis:
      'PTA主力合约TA2609：期货+0.74%，现货+0.35%，持仓+1.42%，盘面资金偏强。\nPVC主力合约V2609：期货-0.52%，现货-0.83%，现货弱于盘面。\nLLDPE主力合约L2609：期现变化温和，短线仍是震荡结构。\nPP主力合约PP2609：现货贴水扩大，低价采购窗口更清晰。',
    fundamentals_analysis:
      'PTA：聚酯刚需仍在，现货跟涨不激进，适合小单补库。\nPVC：地产链需求恢复偏慢，低价资源可逢低分批。\nLLDPE：进口和下游订单扰动并存，维持安全库存。\nPP：现货贴水反映成交偏弱，但低价资源对刚需有吸引力。',
    macro_analysis:
      '美元兑人民币、布伦特原油、中国PMI、美国PMI共同影响大宗商品风险偏好和成本端。中国经济决定内需和终端订单，美国经济影响外需、美元和全球风险偏好；原油通过能源成本传导到化工、油脂和有色估值。',
    policy_analysis:
      '关注能耗、安全生产、环保检查、地产链支持政策，以及交易所保证金和限仓调整。政策窗口期内建议后台人工复核后再推送。',
    status: 'published',
    generated_at: '2026-07-09T17:30:00',
    published_at: '2026-07-09T17:32:00',
    pushed_at: null,
    recommendations: [
      {
        id: 1,
        product_code: 'PTA',
        action: '小单补库',
        basis: 'PTA盘面偏强，现货跟涨温和，刚需采购可保持小单节奏。',
        risk_note: '关注原油和聚酯开工波动，避免高位集中补库。',
        confidence: 76
      },
      {
        id: 2,
        product_code: 'PVC',
        action: '逢低采购',
        basis: 'PVC现货较期货小幅贴水，价格处于近期偏低区间。',
        risk_note: '地产需求恢复仍需观察，库存不宜一次性抬高。',
        confidence: 70
      },
      {
        id: 3,
        product_code: 'LLDPE',
        action: '观望等待',
        basis: 'LLDPE期现价差不大，短线缺少明确采购窗口。',
        risk_note: '若原油或进口到港扰动增强，需调整补库节奏。',
        confidence: 66
      },
      {
        id: 4,
        product_code: 'PP',
        action: '积极采购',
        basis: 'PP现货贴水扩大，低价资源适合分批锁定。',
        risk_note: '需求端订单不足时，建议保留部分现金仓位。',
        confidence: 82
      },
      {
        id: 5,
        product_code: 'OCT',
        action: '观望等待',
        basis: '辛醇暂按现货品种跟踪，等待华东、华南、西南区域报价、库存和开工率给出更明确采购窗口。',
        risk_note: '关注丁辛醇装置开工、增塑剂需求和现货报价样本偏差。',
        confidence: 66
      }
    ]
  },
  products: [
    {
      code: 'PTA',
      name: 'PTA',
      futures_contract: 'TA2609',
      futures_close: 5862,
      spot_price: 5910,
      basis_value: 48,
      futures_change_pct: 0.74,
      spot_change_pct: 0.35,
      open_interest_change_pct: 1.42,
      recommendation: '小单补库',
      confidence: 76
    },
    {
      code: 'PVC',
      name: 'PVC',
      futures_contract: 'V2609',
      futures_close: 5620,
      spot_price: 5580,
      basis_value: -40,
      futures_change_pct: -0.52,
      spot_change_pct: -0.83,
      open_interest_change_pct: 0.66,
      recommendation: '逢低采购',
      confidence: 70
    },
    {
      code: 'LLDPE',
      name: '线型低密度聚乙烯',
      futures_contract: 'L2609',
      futures_close: 8190,
      spot_price: 8250,
      basis_value: 60,
      futures_change_pct: 0.18,
      spot_change_pct: 0.12,
      open_interest_change_pct: -0.41,
      recommendation: '观望等待',
      confidence: 66
    },
    {
      code: 'PP',
      name: '聚丙烯',
      futures_contract: 'PP2609',
      futures_close: 7442,
      spot_price: 7380,
      basis_value: -62,
      futures_change_pct: -0.34,
      spot_change_pct: -1.08,
      open_interest_change_pct: 2.2,
      recommendation: '积极采购',
      confidence: 82
    },
    {
      code: 'PB',
      name: '沪铅',
      futures_contract: 'PB2608',
      futures_close: 16030,
      spot_price: 16080,
      basis_value: 50,
      futures_change_pct: null,
      spot_change_pct: 0.18,
      open_interest_change_pct: null,
      recommendation: '小单补库',
      confidence: 72
    },
    {
      code: 'P',
      name: '棕榈油',
      futures_contract: 'P2609',
      futures_close: 9279,
      spot_price: 9360,
      basis_value: 81,
      futures_change_pct: null,
      spot_change_pct: 0.26,
      open_interest_change_pct: null,
      recommendation: '观望等待',
      confidence: 68
    },
    {
      code: 'PL',
      name: '丙烯',
      futures_contract: 'PL2609',
      futures_close: 7116,
      spot_price: 7180,
      basis_value: 64,
      futures_change_pct: null,
      spot_change_pct: 0.1,
      open_interest_change_pct: null,
      recommendation: '小单补库',
      confidence: 70
    },
    {
      code: 'PX',
      name: 'PX',
      futures_contract: 'PX2609',
      futures_close: 7758,
      spot_price: 7820,
      basis_value: 62,
      futures_change_pct: null,
      spot_change_pct: 0.15,
      open_interest_change_pct: null,
      recommendation: '观望等待',
      confidence: 66
    },
    {
      code: 'CU',
      name: '沪铜',
      futures_contract: 'CU2609',
      futures_close: 103740,
      spot_price: 103900,
      basis_value: 160,
      futures_change_pct: null,
      spot_change_pct: 0.12,
      open_interest_change_pct: null,
      recommendation: '套保关注',
      confidence: 73
    },
    {
      code: 'OCT',
      name: '辛醇',
      futures_contract: null,
      futures_close: null,
      spot_price: 8200,
      basis_value: null,
      futures_change_pct: null,
      spot_change_pct: 0.12,
      open_interest_change_pct: null,
      recommendation: '观望等待',
      confidence: 66
    }
  ]
}

mockOverview.latest_report.product_analyses = mockOverview.products.map((item) => ({
  product_code: item.code,
  price_behavior: item.futures_contract
    ? `${item.code}主力合约${item.futures_contract}：期货${item.futures_close || '-'}，现货${item.spot_price || '-'}，基差${item.basis_value ?? '-'}。K线/形态：离线样本暂按震荡结构处理，需继续观察头肩顶/底、W底、M顶是否确认。均线/多周期：重点跟踪MA5、MA20、MA60是否同向共振。持仓量：结合价格涨跌判断增仓推动或减仓修复。Al Brooks语境：等待连续趋势K线或二次进入确认。YTC语境：先看高周期方向，再看支撑压力位的突破失败或回踩确认。`
    : `${item.code}（${item.name}）为现货品种，暂不做期货盘面分析。价格行为以华东现货${item.spot_price || '-'}、区域报价、库存、开工率和产业链成本传导为主。`,
  fundamentals: `区域现货：华东${item.spot_price || '-'}，华南${item.spot_price ? item.spot_price + 30 : '-'}，西南${item.spot_price ? item.spot_price - 20 : '-'}。开工率离线样本暂按75%附近处理，需跟踪开工率提升是否带来供应压力。社会库存与工厂库存离线样本暂按平稳处理；库存周期：当前偏主动去库存/观望阶段，需继续跟踪社会库存是否累积、工厂库存是否转移到贸易环节。供需判断：暂未出现明显供需失衡，采购以订单覆盖和安全库存为主。`,
  macro: `美元兑人民币离线样本暂按中性处理；中国经济影响${item.code}内需和终端订单，美国经济影响外需与全球风险偏好。原油通过成本端和产业链传导影响该品种价格，产业链传导需结合上游原料、装置开工、库存和下游订单共同判断。`,
  policy: `每日政策/产业消息：安全生产：关注${item.name}生产、仓储和运输环节。环保：关注排放、能耗和地方环保检查。检修：跟踪相关装置计划检修、临停和重启进度。若出现影响供需平衡的重大事件，政策栏和企业微信会置顶推送。`,
  conclusion: `结论：离线样本按价格行为、基本面、宏观面、政策面综合判断，建议${item.recommendation || '观望等待'}。`
}))

export const mockReports = [
  mockOverview.latest_report,
  {
    ...mockOverview.latest_report,
    id: 2,
    report_date: '2026-07-09',
    session_name: 'morning',
    title: '2026-07-09 PTA/PVC/塑料期现早报',
    generated_at: '2026-07-09T08:30:00',
    published_at: '2026-07-09T08:35:00'
  },
  {
    ...mockOverview.latest_report,
    id: 3,
    report_date: '2026-07-08',
    session_name: 'evening',
    title: '2026-07-08 PTA/PVC/塑料期现晚报',
    generated_at: '2026-07-08T17:30:00',
    published_at: '2026-07-08T17:36:00'
  }
]

export function mockTrend(code) {
  const product = mockOverview.products.find((item) => item.code === code) || mockOverview.products[0]
  const hasFutures = product.futures_close !== null && product.futures_close !== undefined
  const baseFuture = hasFutures ? product.futures_close : product.spot_price || 7000
  const baseSpot = product.spot_price || baseFuture
  return Array.from({ length: 30 }, (_, index) => {
    const wave = Math.sin(index / 4) * baseFuture * 0.01
    const drift = (index - 15) * baseFuture * 0.00035
    return {
      trade_date: `2026-06-${String(10 + index).padStart(2, '0')}`,
      futures_contract: product.futures_contract,
      futures_close: hasFutures ? Math.round(baseFuture + wave + drift) : null,
      spot_price: Math.round(baseSpot + Math.cos(index / 5) * baseSpot * 0.008 + drift * 0.6),
      open_interest: hasFutures ? Math.round(112000 + index * 520 + Math.sin(index / 3) * 4500) : null,
      volume: hasFutures ? Math.round(68000 + index * 300 + Math.cos(index / 2) * 5200) : null
    }
  })
}

export const mockBasisOverview = [
  { code: 'PTA', name: 'PTA', basis_value: 48, basis_label: '升水', futures_close: 5862, spot_price: 5910, futures_contract: 'TA2609', trade_date: '2026-07-13', days_since_last: 73, data_stale: true, percentile: 38.7, zone: '中位区', sample_days: 62, window: 250 },
  { code: 'PVC', name: 'PVC', basis_value: -40, basis_label: '贴水', futures_close: 5620, spot_price: 5580, futures_contract: 'V2609', trade_date: '2026-07-13', days_since_last: 73, data_stale: true, percentile: 24.2, zone: '中位区', sample_days: 62, window: 250 },
  { code: 'CU', name: '沪铜', basis_value: 320, basis_label: '升水', futures_close: 78450, spot_price: 78770, futures_contract: 'CU2609', trade_date: '2026-07-13', days_since_last: 73, data_stale: true, percentile: 61.3, zone: '中位区', sample_days: 62, window: 250 }
]

export const mockBasisDetail = {
  snapshot: mockBasisOverview[0],
  history: [
    { trade_date: '2026-07-09', futures_contract: 'TA2609', futures_close: 5850, spot_price: 5895, basis_value: 45 },
    { trade_date: '2026-07-10', futures_contract: 'TA2609', futures_close: 5855, spot_price: 5900, basis_value: 45 },
    { trade_date: '2026-07-13', futures_contract: 'TA2609', futures_close: 5862, spot_price: 5910, basis_value: 48 }
  ]
}
