(function () {
  const data = window.SANDBOX_DATA;
  const nodeMap = Object.fromEntries(data.nodes.map((item) => [item.id, item]));
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const softClamp = (value, limit) => limit * Math.tanh(value / limit);
  const cleanNumber = (value) => Math.round(value * 1000) / 1000;

  function normalizeShock(id, value) {
    if (!nodeMap[id]) return null;
    return { id, value: clamp(Number(value) || 0, -80, 100) };
  }

  function solve(shocks) {
    const direct = Object.fromEntries(data.nodes.map((item) => [item.id, 0]));
    shocks.map((item) => normalizeShock(item.id, item.value)).filter(Boolean).forEach((item) => { direct[item.id] += item.value; });
    let impacts = { ...direct };
    let lineage = Object.fromEntries(data.nodes.map((item) => [item.id, []]));

    for (let pass = 0; pass < 8; pass += 1) {
      const next = { ...direct };
      const nextLineage = Object.fromEntries(data.nodes.map((item) => [item.id, []]));
      data.edges.forEach((item) => {
        const contribution = impacts[item.from] * item.elasticity * item.lag;
        if (Math.abs(contribution) < 0.03) return;
        next[item.to] += contribution;
        nextLineage[item.to].push({
          from: item.from,
          value: contribution,
          confidence: item.confidence,
          kind: item.kind,
          note: item.note
        });
      });
      data.interactions.forEach((item) => {
        const contribution = impacts[item.a] * impacts[item.b] * item.coefficient;
        if (Math.abs(contribution) < 0.03) return;
        next[item.target] += contribution;
        nextLineage[item.target].push({
          from: item.a + ' × ' + item.b,
          value: contribution,
          confidence: .48,
          kind: 'model',
          note: item.label,
          interaction: true
        });
      });
      Object.keys(next).forEach((id) => { next[id] = softClamp(next[id], 90); });
      impacts = next;
      lineage = nextLineage;
    }

    const results = companyResults(impacts, direct);
    const constraints = data.nodes
      .filter((item) => item.layer === 'constraint')
      .map((item) => ({ ...item, impact: impacts[item.id] || 0 }))
      .filter((item) => item.impact < -3)
      .sort((a, b) => a.impact - b.impact);
    const secondOrder = data.interactions.filter((item) => {
      const contribution = impacts[item.a] * impacts[item.b] * item.coefficient;
      return Math.abs(contribution) > 2;
    });
    const avgValuation = results.reduce((sum, item) => sum + item.valuation, 0) / results.length;
    const confidence = calculateConfidence(shocks, lineage, results);

    return {
      direct,
      impacts: Object.fromEntries(Object.entries(impacts).map(([id, value]) => [id, cleanNumber(value)])),
      lineage,
      companies: results,
      constraints,
      secondOrder,
      industryValue: 100 + avgValuation,
      confidence,
      insight: buildInsight(results, constraints, secondOrder, direct),
      path: buildPath(shocks, impacts, lineage, results)
    };
  }

  function companyResults(impacts, direct) {
    return data.companies.map((company) => {
      let operating = 0;
      const exposureParts = [];
      Object.entries(company.exposures).forEach(([id, weight]) => {
        const value = (impacts[id] || 0) * weight;
        operating += value;
        exposureParts.push({ id, weight, value });
      });
      const revenue = softClamp(operating * company.revenueSensitivity, 62);
      let margin = operating * company.marginSensitivity;
      if (company.supplyPricePenalty && direct.hbmSupply > 0) margin -= direct.hbmSupply * company.supplyPricePenalty;
      if (company.id === 'nvda' && direct.exportControl > 0) margin -= direct.exportControl * .08;
      margin = softClamp(margin, 28);

      let capex = Math.max(0, operating) * company.capexSensitivity;
      if (company.id === 'msft') capex += direct.aiCapex || 0;
      capex = softClamp(capex, 55);
      const fcf = softClamp(revenue * .48 + margin * .72 - capex * .42, 60);
      const ratePenalty = (direct.rates || 0) * company.duration * .23;
      const policyPenalty = ['nvda','amd'].includes(company.id) ? Math.max(0, direct.exportControl || 0) * .10 : 0;
      const growthRerating = clamp(revenue * .10, -5, 6);
      const multipleChange = softClamp(growthRerating - ratePenalty - policyPenalty, 26);
      const valuation = softClamp(fcf * .61 + multipleChange * .82, 58);

      return {
        ...company,
        revenue: cleanNumber(revenue),
        margin: cleanNumber(margin),
        capex: cleanNumber(capex),
        fcf: cleanNumber(fcf),
        multipleChange: cleanNumber(multipleChange),
        valuation: cleanNumber(valuation),
        valueIndex: cleanNumber(100 + valuation),
        exposureParts: exposureParts.sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      };
    });
  }

  function calculateConfidence(shocks, lineage, results) {
    const activeIds = new Set(shocks.map((item) => item.id));
    let weighted = 0;
    let count = 0;
    Object.entries(lineage).forEach(([id, parts]) => {
      if (!parts.length) return;
      if (Math.abs(results.find((item) => item.id === id)?.valuation || 0) < .2 && !activeIds.has(id)) return;
      parts.forEach((part) => { weighted += part.confidence; count += 1; });
    });
    return Math.round((count ? weighted / count : .55) * 100);
  }

  function buildInsight(results, constraints, interactions, direct) {
    if (!Object.values(direct).some((value) => Math.abs(value) > .01)) return '系统处于基线状态。添加冲击后，产业链经营结果与估值指数将在同一口径下重算。';
    const sorted = [...results].sort((a, b) => b.valuation - a.valuation);
    const winner = sorted[0];
    const loser = sorted[sorted.length - 1];
    const bottleneck = constraints[0];
    let reason = bottleneck
      ? '有效供给最紧的环节转向' + bottleneck.label + '，其稀缺性沿下游重新定价。'
      : '供给约束未成为主导，价值变化主要来自需求与财务弹性。';
    if ((direct.aiCapex || 0) < 0 && results.find((item) => item.id === 'msft')?.fcf > 0) {
      reason = '资本开支收缩压低上游收入，却可能阶段性改善云厂商自由现金流，形成反向分化。';
    } else if ((direct.exportControl || 0) > 0) {
      reason = (direct.hbmSupply || 0) > 0
        ? '出口限制压低通用 GPU 的可服务市场，而 HBM 扩产将部分价值转向存储与本地替代路线。'
        : '出口限制压低通用 GPU 的可服务市场，同时提高本地替代路线的相对价值。';
    } else if ((direct.hbmSupply || 0) > 0) {
      reason = 'HBM 放量缓解系统交付约束，但存储厂商的数量收益被价格与扩产支出部分抵消。';
    } else if ((direct.inferenceCost || 0) < 0) {
      reason = '推理成本下降通过需求弹性放大 Token 使用，价值可能从单卡性能转向网络、电力与云服务。';
    } else if ((direct.powerSupply || 0) < 0) {
      reason = '电力接入收紧延迟数据中心上线，并使短期价值从算力设备转向配电、能效与交付能力。';
    }
    const interactionText = interactions.length ? ' 检测到显著交叉效应。' : '';
    const loserText = loser.valuation < -.2 ? loser.name + '承受最大估值压力。' : loser.name + '在本组公司中受益最小。';
    return winner.name + '成为本情景相对受益者，' + loserText + reason + interactionText;
  }

  function buildPath(shocks, impacts, lineage, results) {
    if (!shocks.length) return [];
    const main = [...shocks].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0];
    const path = [{ id: main.id, value: impacts[main.id], note: '用户输入的结构化冲击' }];
    let current = main.id;
    const visited = new Set([current]);
    for (let step = 0; step < 6; step += 1) {
      const candidates = data.edges
        .filter((item) => item.from === current && !visited.has(item.to))
        .map((item) => ({ ...item, score: Math.abs(impacts[current] * item.elasticity * item.lag) }))
        .sort((a, b) => b.score - a.score);
      if (!candidates.length) break;
      const selected = candidates[0];
      current = selected.to;
      visited.add(current);
      path.push({ id: current, value: impacts[current], note: selected.note, confidence: selected.confidence });
      if (nodeMap[current]?.layer === 'company') break;
    }
    if (!path.some((item) => nodeMap[item.id]?.layer === 'company')) {
      const winner = [...results].sort((a, b) => Math.abs(b.valuation) - Math.abs(a.valuation))[0];
      path.push({ id: winner.id, value: winner.valuation, note: '财务桥接与估值重算' });
    }
    return path;
  }

  function parseScenario(text) {
    const normalized = String(text || '').toLowerCase();
    const hits = [];
    data.scenarioDefinitions.forEach((definition) => {
      const indices = definition.patterns.map((pattern) => normalized.indexOf(pattern.toLowerCase())).filter((index) => index >= 0);
      if (!indices.length) return;
      const matchIndex = Math.min(...indices);
      const start = Math.max(0, matchIndex - 8);
      const end = Math.min(normalized.length, matchIndex + 30);
      const segment = normalized.slice(start, end);
      const forwardSegment = normalized.slice(matchIndex, end);
      const numberMatch = forwardSegment.match(/(\d+(?:\.\d+)?)\s*%?/) || segment.match(/(\d+(?:\.\d+)?)\s*%?/);
      let value = numberMatch ? Number(numberMatch[1]) : 20;
      if (/下降|减少|降低|收缩|下跌|削减|放缓/.test(segment)) value = -value;
      if (/上升|增加|提高|扩产|升级|增强|增长/.test(segment)) value = Math.abs(value);
      hits.push({ id: definition.id, value: clamp(value, -80, 100), label: definition.label });
    });
    if (!hits.length) return { shocks: [], error: '没有识别到可映射变量。请尝试输入 HBM、资本开支、推理成本、出口管制、CoWoS、电力或利率。' };
    const unique = [];
    hits.forEach((hit) => {
      const existing = unique.find((item) => item.id === hit.id);
      if (existing) existing.value = hit.value;
      else unique.push(hit);
    });
    return { shocks: unique, error: null };
  }

  window.SANDBOX_ENGINE = { solve, parseScenario, clamp, nodeMap };
}());
