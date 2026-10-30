from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import psycopg
from psycopg import sql
import pymysql

from generic_network_contract import (
    STRUCTURAL_ROLES,
    SUPPORTED_FORMULAS,
    normalize_formula_type,
    normalized_direction,
    parse_json_object,
    role_status,
)


MAX_SYNC_ROWS = 2000
MAX_PAGE_SIZE = 250
NETWORK_METADATA_CODES = {
    "NETWORK_ID", "NETWORK_NAME", "NETWORK_VERSION", "NETWORK_NODES_JSON", "NETWORK_EDGES_JSON",
    "NETWORK_LAYERS_JSON", "NETWORK_METADATA_JSON", "NETWORK_CHAIN_LAYER_NO", "NETWORK_CHAIN_LAYER_NAME",
    "NETWORK_CHAIN_POSITION", "NETWORK_EDITABLE_METRIC_CODE", "NETWORK_EDITABLE_METRIC_NAME",
    "NETWORK_EDITABLE_METRIC_TYPE", "NETWORK_EDITABLE_METRIC_UNIT", "NETWORK_EDITABLE_BASELINE_VALUE",
    "NETWORK_DRIVER_SENSITIVITY", "NETWORK_DRIVER_DIRECTION", "NETWORK_DRIVER_MECHANISM", "NETWORK_STATUS", "NETWORK_KIND", "NETWORK_STATE",
    "NETWORK_LAG_DAYS", "NETWORK_IMPACT_CAP_PCT", "NETWORK_NODE_ID", "NETWORK_NODE_LAYER", "NETWORK_NODE_LABEL", "NETWORK_NODE_DESCRIPTION", "NETWORK_NODE_BASELINE", "NETWORK_NODE_EDITABLE", "NETWORK_NODE_METRIC_CODE", "NETWORK_NODE_METRIC_NAME", "NETWORK_NODE_UNIT", "NETWORK_NODE_VALUE_STATUS", "NETWORK_NODE_TYPE", "NETWORK_EDGE_ID", "NETWORK_EDGE_RELATION_TYPE", "NETWORK_EDGE_STATUS", "NETWORK_EDGE_PARAMETER_STATUS", "NETWORK_EDGE_EVIDENCE_SOURCE", "NETWORK_EDGE_SOURCE", "NETWORK_EDGE_TARGET", "NETWORK_EDGE_DIRECTION", "NETWORK_EDGE_WEIGHT", "NETWORK_EDGE_LAG", "NETWORK_EDGE_CONFIDENCE", "NETWORK_EDGE_MECHANISM", "NETWORK_LAYER_NO", "NETWORK_LAYER_CODE", "NETWORK_LAYER_NAME", "NETWORK_LAYER_SUBTITLE", "NETWORK_LAYER_SORT", "FORMULA_ID", "FORMULA_TYPE", "FORMULA_EXPRESSION", "FORMULA_PARAMETERS", "FORMULA_VERSION", "FORMULA_INVALIDATION", "METRIC_CODE", "METRIC_VALUE", "AS_OF_DATE", "VALUATION_DATE", "EVIDENCE_ID", "EVIDENCE_QUOTE", "EVIDENCE_URL",
}
DIMENSION_CODES = {"ENTITY_CODE", "ENTITY_NAME", "EXCHANGE_CODE", "ENTITY_TYPE", "ANNOUNCEMENT_DATE", "REPORT_PERIOD", "STATEMENT_TYPE", "CURRENCY", "OPDATE", "ROW_KEY", "PRICE_ASOF", "VALUATION_METHOD", "DATA_CUTOFF", "VALUATION_STATUS", *NETWORK_METADATA_CODES}


def _metric(code: str, name: str, kind: str, unit: str | None = None, **extra: Any) -> dict[str, Any]:
    return {"metricCode": code, "metricName": name, "metricType": kind, "unit": unit, **extra}


METRICS = [
    _metric("ENTITY_CODE", "证券代码", "dimension"),
    _metric("ENTITY_NAME", "证券简称", "dimension"),
    _metric("EXCHANGE_CODE", "交易所代码", "dimension"),
    _metric("ENTITY_TYPE", "实体类型", "dimension"),
    _metric("ANNOUNCEMENT_DATE", "公告日期", "dimension"),
    _metric("REPORT_PERIOD", "报告期", "dimension"),
    _metric("STATEMENT_TYPE", "报表类型", "dimension"),
    _metric("CURRENCY", "币种", "dimension"),
    _metric("OPDATE", "数据版本时间", "dimension"),
    _metric("ROW_KEY", "来源行标识", "dimension"),
    _metric("NETWORK_ID", "网络标识", "network_metadata"),
    _metric("NETWORK_NAME", "网络名称", "network_metadata"),
    _metric("NETWORK_VERSION", "网络版本", "network_metadata"),
    _metric("NETWORK_NODES_JSON", "节点定义 JSON", "network_metadata"),
    _metric("NETWORK_EDGES_JSON", "连线定义 JSON", "network_metadata"),
    _metric("NETWORK_LAYERS_JSON", "六层定义 JSON", "network_metadata"),
    _metric("NETWORK_METADATA_JSON", "网络元数据 JSON", "network_metadata"),
    _metric("NETWORK_CHAIN_LAYER_NO", "产业链层级编号", "network_metadata"),
    _metric("NETWORK_CHAIN_LAYER_NAME", "产业链层级名称", "network_metadata"),
    _metric("NETWORK_CHAIN_POSITION", "产业链位置", "network_metadata"),
    _metric("NETWORK_EDITABLE_METRIC_CODE", "可调指标代码", "network_metadata"),
    _metric("NETWORK_EDITABLE_METRIC_NAME", "可调指标名称", "network_metadata"),
    _metric("NETWORK_EDITABLE_METRIC_TYPE", "可调指标类型", "network_metadata"),
    _metric("NETWORK_EDITABLE_METRIC_UNIT", "可调指标单位", "network_metadata"),
    _metric("NETWORK_EDITABLE_BASELINE_VALUE", "可调指标基准值", "network_metadata"),
    _metric("NETWORK_DRIVER_SENSITIVITY", "驱动敏感度", "network_metadata"),
    _metric("NETWORK_STATUS", "网络状态", "network_metadata"),
    _metric("NETWORK_KIND", "网络类型", "network_metadata"),
    _metric("NETWORK_STATE", "网络状态详情", "network_metadata"),
    _metric("NETWORK_DRIVER_DIRECTION", "影响方向", "network_metadata"),
    _metric("NETWORK_DRIVER_MECHANISM", "影响机制", "network_metadata"),
    _metric("NETWORK_LAG_DAYS", "传导滞后天数", "network_metadata"),
    _metric("NETWORK_IMPACT_CAP_PCT", "影响幅度上限", "network_metadata"),
    _metric("NETWORK_NODE_ID", "节点标识", "network_metadata"),
    _metric("NETWORK_NODE_LAYER", "节点层级", "network_metadata"),
    _metric("NETWORK_NODE_LABEL", "节点名称", "network_metadata"),
    _metric("NETWORK_NODE_DESCRIPTION", "节点说明", "network_metadata"),
    _metric("NETWORK_NODE_BASELINE", "节点基准值", "network_metadata"),
    _metric("NETWORK_NODE_EDITABLE", "节点可调状态", "network_metadata"),
    _metric("NETWORK_NODE_METRIC_CODE", "节点指标代码", "network_metadata"),
    _metric("NETWORK_NODE_METRIC_NAME", "节点指标名称", "network_metadata"),
    _metric("NETWORK_NODE_UNIT", "节点指标单位", "network_metadata"),
    _metric("NETWORK_NODE_VALUE_STATUS", "节点数值状态", "network_metadata"),
    _metric("NETWORK_NODE_TYPE", "节点类型", "network_metadata"),
    _metric("NETWORK_EDGE_ID", "关系标识", "network_metadata"),
    _metric("NETWORK_EDGE_RELATION_TYPE", "关系类型", "network_metadata"),
    _metric("NETWORK_EDGE_STATUS", "关系状态", "network_metadata"),
    _metric("NETWORK_EDGE_PARAMETER_STATUS", "关系参数状态", "network_metadata"),
    _metric("NETWORK_EDGE_EVIDENCE_SOURCE", "关系证据来源", "network_metadata"),
    _metric("NETWORK_LAYER_NO", "层级编号", "network_metadata"),
    _metric("NETWORK_LAYER_CODE", "层级代码", "network_metadata"),
    _metric("NETWORK_LAYER_NAME", "层级名称", "network_metadata"),
    _metric("NETWORK_LAYER_SUBTITLE", "层级副标题", "network_metadata"),
    _metric("NETWORK_LAYER_SORT", "层级排序", "network_metadata"),
    _metric("FORMULA_ID", "公式标识", "network_metadata"),
    _metric("FORMULA_TYPE", "公式类型", "network_metadata"),
    _metric("FORMULA_EXPRESSION", "公式表达式", "network_metadata"),
    _metric("FORMULA_PARAMETERS", "公式参数", "network_metadata"),
    _metric("FORMULA_VERSION", "公式版本", "network_metadata"),
    _metric("FORMULA_INVALIDATION", "公式失效条件", "network_metadata"),
    _metric("METRIC_CODE", "指标代码", "dimension"),
    _metric("METRIC_VALUE", "指标数值", "numeric"),
    _metric("AS_OF_DATE", "数据日期", "dimension"),
    _metric("VALUATION_DATE", "估值日期", "dimension"),
    _metric("PRICE_ASOF", "行情日期", "dimension"),
    _metric("CLOSE_PRICE", "收盘价", "price", "CNY_PER_SHARE"),
    _metric("DILUTED_SHARES", "稀释后股数", "stock", "SHARES"),
    _metric("CURRENT_MARKET_CAP", "当前市值", "stock", "CURRENCY"),
    _metric("NON_OPERATING_ASSETS", "非经营性资产", "stock", "CURRENCY"),
    _metric("VALUATION_METHOD", "估值方法", "dimension"),
    _metric("VALUATION_MULTIPLE", "估值倍数", "ratio", "MULTIPLE"),
    _metric("DISCOUNT_RATE", "折现率", "ratio", "%"),
    _metric("TERMINAL_GROWTH", "终值增长率", "ratio", "%"),
    _metric("BASELINE_EQUITY_VALUE", "基准股权价值", "stock", "CURRENCY"),
    _metric("SCENARIO_EQUITY_VALUE", "情景股权价值", "stock", "CURRENCY"),
    _metric("VALUE_CHANGE_AMOUNT", "价值变化金额", "flow", "CURRENCY"),
    _metric("VALUE_CHANGE_PCT", "价值变化比例", "ratio", "%"),
    _metric("UPSIDE_DOWNSIDE_PCT", "上行下行比例", "ratio", "%"),
    _metric("DATA_CUTOFF", "数据截止日", "dimension"),
    _metric("VALUATION_STATUS", "估值状态", "dimension"),
    _metric("NETWORK_EDGE_SOURCE", "关系起点", "network_metadata"),
    _metric("NETWORK_EDGE_TARGET", "关系终点", "network_metadata"),
    _metric("NETWORK_EDGE_DIRECTION", "关系方向", "network_metadata"),
    _metric("NETWORK_EDGE_WEIGHT", "关系权重", "network_metadata"),
    _metric("NETWORK_EDGE_LAG", "关系滞后天数", "network_metadata"),
    _metric("NETWORK_EDGE_CONFIDENCE", "关系置信度", "network_metadata"),
    _metric("NETWORK_EDGE_MECHANISM", "关系机制", "network_metadata"),
    _metric("EVIDENCE_ID", "证据标识", "network_metadata"),
    _metric("EVIDENCE_QUOTE", "证据原文", "network_metadata"),
    _metric("EVIDENCE_URL", "证据链接", "network_metadata"),
    _metric("CASH", "货币资金", "stock", "CURRENCY"),
    _metric("INVENTORY", "存货", "stock", "CURRENCY"),
    _metric("ACCOUNTS_RECEIVABLE", "应收账款", "stock", "CURRENCY"),
    _metric("NOTES_RECEIVABLE", "应收票据", "stock", "CURRENCY"),
    _metric("PREPAYMENTS", "预付款项", "stock", "CURRENCY"),
    _metric("TRADING_FINANCIAL_ASSETS", "交易性金融资产", "stock", "CURRENCY"),
    _metric("TOTAL_ASSETS", "资产总额", "stock", "CURRENCY"),
    _metric("TOTAL_LIABILITIES", "负债总额", "stock", "CURRENCY"),
    _metric("SHORT_TERM_DEBT", "短期借款", "stock", "CURRENCY"),
    _metric("LONG_TERM_DEBT", "长期借款", "stock", "CURRENCY"),
    _metric("BONDS_PAYABLE", "应付债券", "stock", "CURRENCY"),
    _metric("LEASE_LIABILITY", "租赁负债", "stock", "CURRENCY"),
    _metric("CURRENT_PORTION_DEBT", "一年内到期非流动负债", "stock", "CURRENCY"),
    _metric("EQUITY", "归母股东权益", "stock", "CURRENCY"),
    _metric("MINORITY_INTEREST", "少数股东权益", "stock", "CURRENCY"),
    _metric("TOTAL_SHARES", "总股本", "stock", "SHARES"),
    _metric("REVENUE", "营业收入", "flow", "CURRENCY"),
    _metric("OPERATING_COST", "营业成本", "flow", "CURRENCY"),
    _metric("OPERATING_PROFIT", "营业利润", "flow", "CURRENCY"),
    _metric("NET_PROFIT", "归母净利润", "flow", "CURRENCY"),
    _metric("EBIT", "息税前利润", "flow", "CURRENCY"),
    _metric("EBITDA", "息税折旧摊销前利润", "flow", "CURRENCY"),
    _metric("EPS_BASIC", "基本每股收益", "ratio", "CURRENCY_PER_SHARE"),
    _metric("EPS_DILUTED", "稀释每股收益", "ratio", "CURRENCY_PER_SHARE"),
    _metric("OPERATING_CASH_FLOW", "经营活动现金流", "flow", "CURRENCY"),
    _metric("CAPEX", "资本开支", "flow", "CURRENCY"),
    _metric("FREE_CASH_FLOW", "自由现金流", "flow", "CURRENCY"),
    _metric("ENDING_CASH", "期末现金及等价物", "stock", "CURRENCY"),
    _metric("GROSS_PROFIT", "毛利润", "flow", "CURRENCY", networkLayer="chain"),
    _metric("TOTAL_DEBT", "有息债务总额", "stock", "CURRENCY", networkLayer="constraint"),
    _metric("NET_DEBT", "净债务", "stock", "CURRENCY", networkLayer="constraint"),
    _metric("REVENUE_GROWTH_PCT", "营业收入增长率", "ratio", "%", networkLayer="demand", valueStatus="CALCULATED_RESULT"),
    _metric("NET_PROFIT_GROWTH_PCT", "净利润同比增长率", "ratio", "%", networkLayer="chain", valueStatus="CALCULATED_RESULT"),
    _metric("GROSS_MARGIN_PCT", "毛利率", "ratio", "%", networkLayer="chain", valueStatus="CALCULATED_RESULT"),
    _metric("OPERATING_MARGIN_PCT", "营业利润率", "ratio", "%", networkLayer="chain", valueStatus="CALCULATED_RESULT"),
    _metric("NET_MARGIN_PCT", "净利率", "ratio", "%", networkLayer="chain", valueStatus="CALCULATED_RESULT"),
    _metric("FCF_MARGIN_PCT", "自由现金流率", "ratio", "%", networkLayer="chain", valueStatus="CALCULATED_RESULT"),
    _metric("ASSET_LIABILITY_RATIO_PCT", "资产负债率", "ratio", "%", networkLayer="constraint", valueStatus="CALCULATED_RESULT"),
    _metric("JM_PRICE", "焦煤价格", "price", "CNY_PER_TONNE"),
    _metric("STEEL_DEMAND", "钢材需求", "flow", "INDEX"),
    _metric("STEEL_PRICE", "钢材价格", "price", "CNY_PER_TONNE"),
    _metric("STEEL_INVENTORY", "钢材社会库存", "stock", "TONNE"),
    _metric("BLAST_FURNACE_UTILIZATION", "高炉产能利用率", "ratio", "PERCENT"),
]
METRIC_BY_CODE = {item["metricCode"]: item for item in METRICS}

KNOWN_FINANCIAL_FIELD_LABELS = {
    "cash_cash_equ_end_period": "期末现金及现金等价物余额",
    "cash_paid_invest": "投资支付的现金",
    "cash_pay_acq_const_fiolta": "购建固定资产及长期资产支付的现金",
    "cash_pay_dist_dpcp_int_exp": "分配股利、利润或偿付利息支付的现金",
    "cash_prepay_amt_borr": "偿还债务支付的现金",
    "cash_recp_borrow": "取得借款收到的现金",
    "cash_recp_cap_contrib": "吸收投资收到的现金",
    "cash_recp_disp_withdrwl_invest": "收回投资收到的现金",
    "cash_recp_return_invest": "取得投资收益收到的现金",
    "cash_recp_sg_and_rs": "销售商品及提供劳务收到的现金",
    "eff_fx_flu_cash": "汇率变动对现金的影响",
    "handling_chrg_paid": "支付手续费及佣金的现金",
    "net_cash_flows_oper_act": "经营活动产生的现金流量净额",
    "net_cash_recp_disp_fiolta": "处置固定资产及长期资产收回的现金净额",
    "net_cash_recp_disp_sobu": "处置子公司收到的现金净额",
    "net_incr_cash_cash_equ": "现金及现金等价物净增加额",
    "net_incr_clients_loan_adv": "客户贷款及垫款净增加额",
    "net_incr_int_handling_chrg": "利息及手续费现金净增加额",
    "net_incr_loans_other_bank": "向其他金融机构借款净增加额",
    "opmode": "经营模式代码",
    "other_cash_pay_ral_inv_act": "支付其他与投资活动有关的现金",
    "other_cash_pay_ral_oper_act": "支付其他与经营活动有关的现金",
    "other_cash_recp_ral_fnc_act": "收到其他与筹资活动有关的现金",
    "pay_all_typ_tax": "支付的各项税费",
    "recp_tax_rends": "收到的税费返还",
    "spe_bal_cash_inflows_fnc": "筹资活动现金流入特殊项目",
    "spe_bal_cash_inflows_oper": "经营活动现金流入特殊项目",
    "spe_bal_cash_outflows_fnc": "筹资活动现金流出特殊项目",
    "stot_cash_inflows_fnc_act": "筹资活动现金流入小计",
    "stot_cash_outflows_inv_act": "投资活动现金流出小计",
    "stot_cash_outflows_oper_act": "经营活动现金流出小计",
    "im_net_cash_flows_oper_act": "经营活动现金流量净额（间接法）",
    "other_cash_pay_ral_fnc_act": "支付其他与筹资活动有关的现金",
    "securitie_netcash_received": "证券业务收到的现金净额",
    "incl_cash_rec_saims": "其中：业务活动收到的现金",
    "net_incr_dep_cob": "客户存款和同业存放款项净增加额",
    "net_incr_insured_dep": "保户储金及投资款净增加额",
    "s_dismantle_capital_add_net": "拆出资金净增加额",
    "net_cash_pay_aquis_sobu": "取得子公司支付的现金净额",
    "comp_type_code": "公司类型代码",
    "net_cash_received_reinsu_bus": "再保险业务收到的现金净额",
    "cash_pay_claims_orig_inco": "支付原保险合同赔付款项的现金",
    "spe_bal_cash_outflows_inv": "投资活动现金流出特殊项目",
    "invest_loss": "投资损失",
    "depr_fa_coga_dpba": "固定资产及生产性资产折旧",
    "incr_oper_payable": "经营性应付项目增加额",
    "net_cash_flows_fnc_act": "筹资活动产生的现金流量净额",
    "other_cash_recp_ral_oper_act": "收到其他与经营活动有关的现金",
    "other_cash_recp_ral_inv_act": "收到其他与投资活动有关的现金",
    "stot_cash_inflows_oper_act": "经营活动现金流入小计",
    "stot_cash_outflows_fnc_act": "筹资活动现金流出小计",
    "stot_cash_inflows_inv_act": "投资活动现金流入小计",
    "net_cash_flows_inv_act": "投资活动产生的现金流量净额",
    "spe_bal_cash_outflows_oper": "经营活动现金流出特殊项目",
    "cash_pay_goods_purch_serv_rec": "购买商品及接受劳务支付的现金",
    "cash_pay_beh_empl": "支付给职工以及为职工支付的现金",
    "cash_cash_equ_beg_period": "期初现金及现金等价物余额",
    "melt_money_net_increase": "拆入资金净增加额",
    "proc_issue_bonds": "发行债券收到的现金",
    "oper_mode": "经营模式代码",
}


ALIASES = {
    "s_info_windcode": "ENTITY_CODE", "wind_code": "ENTITY_CODE", "security_code": "ENTITY_CODE", "entity_code": "ENTITY_CODE", "company_code": "ENTITY_CODE", "ticker_code": "ENTITY_CODE", "ticker": "ENTITY_CODE",
    "证券代码": "ENTITY_CODE", "股票代码": "ENTITY_CODE", "公司代码": "ENTITY_CODE", "主体代码": "ENTITY_CODE",
    "entity_name": "ENTITY_NAME", "company_name": "ENTITY_NAME", "security_name": "ENTITY_NAME", "ticker_name": "ENTITY_NAME",
    "证券简称": "ENTITY_NAME", "股票简称": "ENTITY_NAME", "公司简称": "ENTITY_NAME", "公司名称": "ENTITY_NAME", "证券名称": "ENTITY_NAME",
    "ann_dt": "ANNOUNCEMENT_DATE", "actual_ann_dt": "ANNOUNCEMENT_DATE", "announcement_date": "ANNOUNCEMENT_DATE",
    "公告日期": "ANNOUNCEMENT_DATE", "实际公告日期": "ANNOUNCEMENT_DATE", "披露日期": "ANNOUNCEMENT_DATE", "发布日期": "ANNOUNCEMENT_DATE",
    "report_period": "REPORT_PERIOD", "statement_type": "STATEMENT_TYPE", "crncy_code": "CURRENCY", "currency": "CURRENCY",
    "报告期": "REPORT_PERIOD", "报告日期": "REPORT_PERIOD", "财报日期": "REPORT_PERIOD", "报表类型": "STATEMENT_TYPE", "币种": "CURRENCY",
    "opdate": "OPDATE", "object_id": "ROW_KEY", "record_id": "ROW_KEY",
    "更新时间": "OPDATE", "数据更新时间": "OPDATE", "版本时间": "OPDATE", "入库时间": "OPDATE", "主键": "ROW_KEY", "行标识": "ROW_KEY",
    "network_id": "NETWORK_ID", "networkid": "NETWORK_ID", "网络标识": "NETWORK_ID", "网络id": "NETWORK_ID",
    "network_name": "NETWORK_NAME", "networkname": "NETWORK_NAME", "网络名称": "NETWORK_NAME",
    "network_version": "NETWORK_VERSION", "schema_version": "NETWORK_VERSION", "网络版本": "NETWORK_VERSION", "结构版本": "NETWORK_VERSION",
    "network_status": "NETWORK_STATUS", "network_kind": "NETWORK_KIND", "network_state": "NETWORK_STATE",
    "node_id": "NETWORK_NODE_ID", "nodeid": "NETWORK_NODE_ID", "node_code": "NETWORK_NODE_ID", "node_key": "NETWORK_NODE_ID", "layer": "NETWORK_NODE_LAYER", "node_description": "NETWORK_NODE_DESCRIPTION", "baseline_value": "NETWORK_NODE_BASELINE", "baseline": "NETWORK_NODE_BASELINE", "editable": "NETWORK_NODE_EDITABLE", "metric_code": "NETWORK_NODE_METRIC_CODE", "metric_name": "NETWORK_NODE_METRIC_NAME", "unit": "NETWORK_NODE_UNIT", "value_status": "NETWORK_NODE_VALUE_STATUS", "node_type": "NETWORK_NODE_TYPE", "node_layer": "NETWORK_NODE_LAYER", "layer_id": "NETWORK_NODE_LAYER", "layer_no": "NETWORK_NODE_LAYER", "chain_layer_no": "NETWORK_NODE_LAYER", "chain_layer_name": "NETWORK_NODE_LAYER", "node_label": "NETWORK_NODE_LABEL", "node_name": "NETWORK_NODE_LABEL", "node_name_cn": "NETWORK_NODE_LABEL", "node_title": "NETWORK_NODE_LABEL",
    "edge_id": "NETWORK_EDGE_ID", "relation_type": "NETWORK_EDGE_RELATION_TYPE", "edge_type": "NETWORK_EDGE_RELATION_TYPE", "source_node_id": "NETWORK_EDGE_SOURCE", "source_node": "NETWORK_EDGE_SOURCE", "source_id": "NETWORK_EDGE_SOURCE", "from_node": "NETWORK_EDGE_SOURCE", "target_node_id": "NETWORK_EDGE_TARGET", "target_node": "NETWORK_EDGE_TARGET", "target_id": "NETWORK_EDGE_TARGET", "to_node": "NETWORK_EDGE_TARGET", "source": "NETWORK_EDGE_SOURCE", "target": "NETWORK_EDGE_TARGET", "direction": "NETWORK_EDGE_DIRECTION", "edge_direction": "NETWORK_EDGE_DIRECTION", "weight": "NETWORK_EDGE_WEIGHT", "edge_weight": "NETWORK_EDGE_WEIGHT", "lag_days": "NETWORK_EDGE_LAG", "edge_lag_days": "NETWORK_EDGE_LAG", "confidence": "NETWORK_EDGE_CONFIDENCE", "edge_confidence": "NETWORK_EDGE_CONFIDENCE", "mechanism": "NETWORK_EDGE_MECHANISM", "edge_mechanism": "NETWORK_EDGE_MECHANISM", "status": "NETWORK_EDGE_STATUS", "parameter_status": "NETWORK_EDGE_PARAMETER_STATUS", "evidence_source": "NETWORK_EDGE_EVIDENCE_SOURCE",
    "evidence_id": "EVIDENCE_ID", "original_quote": "EVIDENCE_QUOTE", "source_url": "EVIDENCE_URL",
    "entity_name_cn": "ENTITY_NAME", "company_name_cn": "ENTITY_NAME", "exchange_code": "ENTITY_CODE", "entity_type": "ENTITY_TYPE",
    "nodes": "NETWORK_NODES_JSON", "nodes_json": "NETWORK_NODES_JSON", "node_json": "NETWORK_NODES_JSON", "network_nodes": "NETWORK_NODES_JSON", "network_nodes_json": "NETWORK_NODES_JSON", "节点": "NETWORK_NODES_JSON", "节点json": "NETWORK_NODES_JSON", "网络节点": "NETWORK_NODES_JSON", "网络节点json": "NETWORK_NODES_JSON",
    "edges": "NETWORK_EDGES_JSON", "edges_json": "NETWORK_EDGES_JSON", "edge_json": "NETWORK_EDGES_JSON", "network_edges": "NETWORK_EDGES_JSON", "network_edges_json": "NETWORK_EDGES_JSON", "关系": "NETWORK_EDGES_JSON", "连线": "NETWORK_EDGES_JSON", "连线json": "NETWORK_EDGES_JSON", "网络关系": "NETWORK_EDGES_JSON", "网络关系json": "NETWORK_EDGES_JSON",
    "layers_json": "NETWORK_LAYERS_JSON", "layer_labels_json": "NETWORK_LAYERS_JSON", "network_layers_json": "NETWORK_LAYERS_JSON", "六层定义json": "NETWORK_LAYERS_JSON",
    "network_metadata": "NETWORK_METADATA_JSON", "network_metadata_json": "NETWORK_METADATA_JSON", "网络元数据": "NETWORK_METADATA_JSON", "网络元数据json": "NETWORK_METADATA_JSON",
    "network_json": "NETWORK_METADATA_JSON", "graph_json": "NETWORK_METADATA_JSON", "network_definition": "NETWORK_METADATA_JSON", "network_definition_json": "NETWORK_METADATA_JSON", "网络_json": "NETWORK_METADATA_JSON", "网络json": "NETWORK_METADATA_JSON", "网络定义": "NETWORK_METADATA_JSON", "网络定义_json": "NETWORK_METADATA_JSON", "网络定义json": "NETWORK_METADATA_JSON",
    "monetary_cap": "CASH", "cash": "CASH", "inventories": "INVENTORY", "inventory": "INVENTORY",
    "acct_rcv": "ACCOUNTS_RECEIVABLE", "accounts_receivable": "ACCOUNTS_RECEIVABLE", "notes_rcv": "NOTES_RECEIVABLE",
    "prepay": "PREPAYMENTS", "tradable_fin_assets": "TRADING_FINANCIAL_ASSETS", "tot_assets": "TOTAL_ASSETS", "total_assets": "TOTAL_ASSETS",
    "tot_liab": "TOTAL_LIABILITIES", "total_liabilities": "TOTAL_LIABILITIES", "st_borrow": "SHORT_TERM_DEBT", "short_term_debt": "SHORT_TERM_DEBT", "lt_borrow": "LONG_TERM_DEBT", "long_term_debt": "LONG_TERM_DEBT",
    "bonds_payable": "BONDS_PAYABLE", "lease_liab": "LEASE_LIABILITY", "lease_liability": "LEASE_LIABILITY", "non_cur_liab_due_within_1y": "CURRENT_PORTION_DEBT",
    "tot_shrhldr_eqy_excl_min_int": "EQUITY", "equity": "EQUITY", "minority_int": "MINORITY_INTEREST", "tot_shr": "TOTAL_SHARES", "total_shares": "TOTAL_SHARES",
    "tot_oper_rev": "REVENUE", "oper_rev": "REVENUE", "revenue": "REVENUE", "less_oper_cost": "OPERATING_COST",
    "operating_cost": "OPERATING_COST", "oper_profit": "OPERATING_PROFIT", "operating_profit": "OPERATING_PROFIT",
    "net_profit_excl_min_int_inc": "NET_PROFIT", "net_profit": "NET_PROFIT", "ebit": "EBIT", "ebitda": "EBITDA",
    "s_fa_eps_basic": "EPS_BASIC", "s_fa_eps_diluted": "EPS_DILUTED",
    "net_cash_flows_oper_act": "OPERATING_CASH_FLOW", "operating_cash_flow": "OPERATING_CASH_FLOW",
    "cash_pay_acq_const_fiolta": "CAPEX", "capex": "CAPEX", "free_cash_flow": "FREE_CASH_FLOW",
    "cash_cash_equ_end_period": "ENDING_CASH", "ending_cash": "ENDING_CASH",
    "gross_profit": "GROSS_PROFIT", "total_debt": "TOTAL_DEBT", "net_debt": "NET_DEBT",
    "revenue_growth_pct": "REVENUE_GROWTH_PCT", "net_profit_growth_pct": "NET_PROFIT_GROWTH_PCT",
    "gross_margin_pct": "GROSS_MARGIN_PCT", "operating_margin_pct": "OPERATING_MARGIN_PCT",
    "net_margin_pct": "NET_MARGIN_PCT", "fcf_margin_pct": "FCF_MARGIN_PCT",
    "asset_liability_ratio_pct": "ASSET_LIABILITY_RATIO_PCT",
    "price_asof": "PRICE_ASOF", "close_price": "CLOSE_PRICE", "diluted_shares": "DILUTED_SHARES", "current_market_cap": "CURRENT_MARKET_CAP", "non_operating_assets": "NON_OPERATING_ASSETS", "valuation_method": "VALUATION_METHOD", "valuation_multiple": "VALUATION_MULTIPLE", "discount_rate": "DISCOUNT_RATE", "terminal_growth": "TERMINAL_GROWTH", "baseline_equity_value": "BASELINE_EQUITY_VALUE", "scenario_equity_value": "SCENARIO_EQUITY_VALUE", "value_change_amount": "VALUE_CHANGE_AMOUNT", "value_change_pct": "VALUE_CHANGE_PCT", "upside_downside_pct": "UPSIDE_DOWNSIDE_PCT", "data_cutoff": "DATA_CUTOFF", "valuation_status": "VALUATION_STATUS",
    "chain_layer_no": "NETWORK_CHAIN_LAYER_NO", "chain_layer_name": "NETWORK_CHAIN_LAYER_NAME", "chain_position": "NETWORK_CHAIN_POSITION",
    "editable_metric_code": "NETWORK_EDITABLE_METRIC_CODE", "editable_metric_name": "NETWORK_EDITABLE_METRIC_NAME",
    "editable_metric_type": "NETWORK_EDITABLE_METRIC_TYPE", "editable_metric_unit": "NETWORK_EDITABLE_METRIC_UNIT",
    "editable_baseline_value": "NETWORK_EDITABLE_BASELINE_VALUE", "driver_sensitivity": "NETWORK_DRIVER_SENSITIVITY",
    "driver_direction": "NETWORK_DRIVER_DIRECTION", "impact_direction": "NETWORK_DRIVER_DIRECTION",
    "driver_mechanism": "NETWORK_DRIVER_MECHANISM", "impact_mechanism": "NETWORK_DRIVER_MECHANISM",
    "lag_days": "NETWORK_LAG_DAYS", "impact_cap_pct": "NETWORK_IMPACT_CAP_PCT",
    "coking_coal_price": "JM_PRICE", "steel_demand": "STEEL_DEMAND",
    "steel_price": "STEEL_PRICE", "steel_inventory": "STEEL_INVENTORY", "blast_furnace_utilization": "BLAST_FURNACE_UTILIZATION",
}

ROLE_ALIASES = {
    "LAYERS": {"layer_no": "NETWORK_LAYER_NO", "layer_code": "NETWORK_LAYER_CODE", "layer_name": "NETWORK_LAYER_NAME", "layer_name_cn": "NETWORK_LAYER_NAME", "layer_label": "NETWORK_LAYER_NAME", "layer_subtitle": "NETWORK_LAYER_SUBTITLE", "layer_subtitle_cn": "NETWORK_LAYER_SUBTITLE", "sort_order": "NETWORK_LAYER_SORT"},
    "NODES": {"metric_code": "NETWORK_NODE_METRIC_CODE", "metric_name": "NETWORK_NODE_METRIC_NAME", "unit": "NETWORK_NODE_UNIT", "baseline_value": "NETWORK_NODE_BASELINE", "editable": "NETWORK_NODE_EDITABLE", "value_status": "NETWORK_NODE_VALUE_STATUS"},
    "EDGES": {"edge_id": "NETWORK_EDGE_ID", "relation_type": "NETWORK_EDGE_RELATION_TYPE", "edge_type": "NETWORK_EDGE_RELATION_TYPE", "formula_id": "FORMULA_ID", "formula_type": "FORMULA_TYPE", "parameters_json": "FORMULA_PARAMETERS", "status": "NETWORK_EDGE_STATUS", "parameter_status": "NETWORK_EDGE_PARAMETER_STATUS"},
    "FORMULAS": {"formula_id": "FORMULA_ID", "formula_type": "FORMULA_TYPE", "formula_code": "FORMULA_TYPE", "formula_expression": "FORMULA_EXPRESSION", "expression": "FORMULA_EXPRESSION", "parameters_json": "FORMULA_PARAMETERS", "parameters": "FORMULA_PARAMETERS", "formula_version": "FORMULA_VERSION", "invalidation": "FORMULA_INVALIDATION", "invalidation_condition": "FORMULA_INVALIDATION"},
    "METRIC_VALUES": {"metric_code": "METRIC_CODE", "metric_id": "METRIC_CODE", "value": "METRIC_VALUE", "metric_value": "METRIC_VALUE", "as_of_date": "AS_OF_DATE"},
    "VALUATION": {"valuation_date": "VALUATION_DATE", "price_asof": "PRICE_ASOF", "as_of_date": "AS_OF_DATE", "close_price": "CLOSE_PRICE", "diluted_shares": "DILUTED_SHARES", "current_market_cap": "CURRENT_MARKET_CAP", "net_debt": "NET_DEBT", "non_operating_assets": "NON_OPERATING_ASSETS", "valuation_method": "VALUATION_METHOD", "valuation_multiple": "VALUATION_MULTIPLE", "discount_rate": "DISCOUNT_RATE", "terminal_growth": "TERMINAL_GROWTH", "baseline_equity_value": "BASELINE_EQUITY_VALUE", "scenario_equity_value": "SCENARIO_EQUITY_VALUE", "value_change_amount": "VALUE_CHANGE_AMOUNT", "value_change_pct": "VALUE_CHANGE_PCT", "upside_downside_pct": "UPSIDE_DOWNSIDE_PCT", "data_cutoff": "DATA_CUTOFF", "valuation_status": "VALUATION_STATUS"},
}

NUMERIC_TYPE_TOKENS = ("int", "numeric", "decimal", "double", "real", "float", "money", "number")
DOMAIN_SPECIFIC_CODES = {"JM_PRICE", "STEEL_DEMAND", "STEEL_PRICE", "STEEL_INVENTORY", "BLAST_FURNACE_UTILIZATION"}


def _is_numeric_type(value: Any) -> bool:
    dtype = str(value or "").lower()
    return any(token in dtype for token in NUMERIC_TYPE_TOKENS)


def _custom_metric(column: dict[str, Any]) -> dict[str, Any]:
    source_name = str(column.get("columnName") or column.get("column") or "自定义指标").strip()
    column_comment = str(column.get("columnComment") or "").strip()
    generic = re.fullmatch(r"(?:column|col|c)[_-]?(\d+)", source_name, re.IGNORECASE)
    known_label = KNOWN_FINANCIAL_FIELD_LABELS.get(source_name.lower())
    name = column_comment[:80] if re.search(r"[\u4e00-\u9fff]", column_comment) else (known_label or (f"待识别指标 {generic.group(1)}" if generic else source_name))
    locator = column.get("sourceLocator") or column.get("column") or source_name
    code = "CUSTOM_" + hashlib.sha256(json.dumps(locator, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12].upper()
    normalized = name.lower()
    kind = "score" if any(token in normalized for token in ("得分", "评分", "能力", "质量", "效率", "风险")) else "numeric"
    unit = "SCORE" if kind == "score" else "SOURCE_UNIT_UNKNOWN"
    return {"metricCode": code, "metricName": name, "metricType": kind, "unit": unit, "description": column_comment[:240] or ("内置财务字段词典识别" if known_label else None), "sourceDefined": True, "semanticSource": "COLUMN_COMMENT" if column_comment else ("FINANCIAL_FIELD_DICTIONARY" if known_label else None)}


def _metric_for_mapping(item: dict[str, Any]) -> dict[str, Any] | None:
    return METRIC_BY_CODE.get(str(item.get("metricCode") or "")) or (
        item.get("metricDefinition") if isinstance(item.get("metricDefinition"), dict) else None
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def leaf(source_field: str) -> str:
    return source_field.rsplit(".", 1)[-1].strip().lower().replace("-", "_").replace(" ", "_")


def safe_identifier(value: Any, key: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 128 or any(char == "\x00" or unicodedata.category(char).startswith("C") for char in text):
        raise ValueError(f"DB_IDENTIFIER_INVALID:{key}")
    return text


def _database_password(config: dict[str, Any]) -> str | None:
    password = config.get("password")
    if password not in (None, ""):
        return str(password)
    reference = str(config.get("credentialRef") or "").strip()
    if not reference:
        return None
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", reference):
        raise ValueError("CREDENTIAL_REFERENCE_INVALID")
    if reference not in os.environ:
        raise ValueError("CREDENTIAL_REFERENCE_NOT_FOUND")
    return os.environ[reference]


def rule_candidates(columns: list[dict[str, Any]], source_id: str, network_intent: str = "EXTEND_EXISTING") -> list[dict[str, Any]]:
    output = []
    for column in columns:
        source_field = str(column.get("column") or "")
        # The structured locator is authoritative: a literal column name may itself contain dots.
        field = leaf(str(column.get("columnName") or source_field))
        role = str(column.get("tableRole") or "UNKNOWN")
        code = str(column.get("precompiledRole") or "") or ROLE_ALIASES.get(role, {}).get(field) or ALIASES.get(field)
        if network_intent == "CREATE_NEW_NETWORK" and code in DOMAIN_SPECIFIC_CODES:
            code = None
        metric = METRIC_BY_CODE.get(code or "")
        custom = not metric and (_is_numeric_type(column.get("dtype")) or float(column.get("numericSampleRate") or 0) >= 0.8)
        if custom:
            metric = _custom_metric(column)
            code = metric["metricCode"]
        output.append({
            "mappingId": stable_id("MAP", {"sourceId": source_id, "locator": column.get("sourceLocator") or source_field}),
            "sourceId": source_id,
            "sourceField": source_field,
            "sourceColumn": source_field,
            "metricCode": code or "UNRESOLVED",
            "metricName": metric["metricName"] if metric else "尚未识别",
            "confidence": 0.99 if code in DIMENSION_CODES else (0.94 if metric and not custom else (0.9 if custom and metric.get("semanticSource") in {"COLUMN_COMMENT", "FINANCIAL_FIELD_DICTIONARY"} else (0.68 if custom else 0.0))),
            "reason": "标准字段词典精确匹配" if metric and not custom else ((("数据库列注释提供中文业务含义" if metric.get("semanticSource") == "COLUMN_COMMENT" else "内置财务字段词典提供中文业务含义")+"，仍需人工确认" if metric.get("semanticSource") in {"COLUMN_COMMENT", "FINANCIAL_FIELD_DICTIONARY"} else ("技术列名仅能确定为数值字段，需先由 AI 结合样例生成中文语义" if re.fullmatch(r"(?:column|col|c)[_-]?\d+", str(column.get("columnName") or ""), re.IGNORECASE) else "数值列可作为来源自定义指标，需人工确认含义与单位")) if custom else "规则词典未识别，可请求 AI 候选或人工选择"),
            "evidence": ["STANDARD_METRIC_DICTIONARY_V1.1"] if metric and not custom else (["SOURCE_SCHEMA_NUMERIC_TYPE"] if custom else ["SCHEMA_PROFILE"]),
            "candidateSource": "RULE" if metric and not custom else ("CUSTOM_NUMERIC" if custom else "RULE_UNRESOLVED"),
            "status": "PENDING_REVIEW" if metric else "UNRESOLVED",
            "suggestedAction": "MAP" if metric else None,
            "metricDefinition": metric,
            "sourceLocator": column.get("sourceLocator"),
            "databaseName": column.get("databaseName"),
            "schemaName": column.get("schemaName"),
            "tableName": column.get("tableName"),
            "columnName": column.get("columnName"),
            "dataType": column.get("dtype"),
            "columnComment": column.get("columnComment"), "tableRole": role,
        })
    return output


def table_adapter_candidates(adapters: list[dict[str, Any]], existing: list[dict[str, Any]], source_id: str, network_intent: str = "EXTEND_EXISTING") -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for adapter in adapters:
        table = adapter.get("tableName")
        table_items = [item for item in existing if (item.get("sourceLocator") or {}).get("table") == table]
        present = {item.get("metricCode") for item in table_items}
        locator = {"database": adapter.get("databaseName"), "schema": adapter.get("schemaName"), "table": table, "column": None}
        definitions = []
        role = str(adapter.get("networkRole") or "UNKNOWN")
        if role not in STRUCTURAL_ROLES and network_intent == "CREATE_NEW_NETWORK" and not present.intersection({"ENTITY_CODE", "ENTITY_NAME", "ROW_KEY"}):
            definitions.append(("ENTITY_CODE", "自动行标识", "ROW_HASH", None, "原表没有实体键；确认后按当前行内容生成稳定标识"))
        if role not in STRUCTURAL_ROLES and "REPORT_PERIOD" not in present and adapter.get("reportPeriodHint"):
            definitions.append(("REPORT_PERIOD", "表级报告期", "CONSTANT", adapter["reportPeriodHint"], "从表名年份推断，确认后使用"))
        if role not in STRUCTURAL_ROLES and not present.intersection({"ANNOUNCEMENT_DATE", "OPDATE"}):
            definitions.append(("ANNOUNCEMENT_DATE", "表级数据可见日", "SYNC_CUTOFF", None, "原表无公告日；使用本次同步截止日，仅代表快照可见边界"))
        for code, label, value_mode, constant, reason in definitions:
            metric = METRIC_BY_CODE[code]
            field = f"[表参数] {adapter.get('schemaName')}.{table}.{label}"
            output.append({
                "mappingId": stable_id("MAP", {"sourceId": source_id, "table": locator, "virtual": code}),
                "sourceId": source_id, "sourceField": field, "sourceColumn": None,
                "metricCode": code, "metricName": metric["metricName"], "metricDefinition": metric,
                "confidence": 0.72 if value_mode == "CONSTANT" else 0.55, "reason": reason,
                "evidence": ["TABLE_NAME_INFERENCE"] if value_mode == "CONSTANT" else ["SNAPSHOT_CUTOFF_POLICY"],
                "candidateSource": "TABLE_ADAPTER", "status": "PENDING_REVIEW", "suggestedAction": "MAP",
                "sourceLocator": locator, "databaseName": locator["database"], "schemaName": locator["schema"],
                "tableName": table, "columnName": label, "dataType": "virtual",
                "valueMode": value_mode, "constantValue": constant,
            })
    return output


def auto_confirm_precompiled_candidates(adapters: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    precompiled_adapters = [item for item in adapters if str(item.get("adapterMode") or "").startswith("PRECOMPILED_NETWORK_") or str(item.get("adapterMode") or "").startswith("MULTI_TABLE_")]
    tables = {item.get("tableName") for item in precompiled_adapters}
    modes = sorted({str(item.get("adapterMode")) for item in precompiled_adapters})
    columnar_only = any(mode == "PRECOMPILED_NETWORK_COLUMNS" for mode in modes)
    confirmed = 0
    unresolved = 0
    if not tables:
        return {"detected": False, "tables": [], "adapterModes": [], "autoConfirmed": 0, "needsReview": 0}
    for item in candidates:
        if item.get("tableName") not in tables:
            continue
        source = item.get("candidateSource")
        code = str(item.get("metricCode") or "")
        if columnar_only and code in {"NETWORK_NODES_JSON", "NETWORK_EDGES_JSON", "NETWORK_LAYERS_JSON", "NETWORK_METADATA_JSON"}:
            item.update({"status": "IGNORED", "suggestedAction": "IGNORE", "ignoredReason": "列式预编译表不使用 JSON 节点字段"})
            continue
        deterministic = source in {"RULE", "TABLE_ADAPTER"} or (source == "CUSTOM_NUMERIC" and code.startswith("CUSTOM_"))
        if deterministic and code != "UNRESOLVED":
            item.update({
                "status": "CONFIRMED", "confirmedAt": now(), "confirmedBy": "PRECOMPILED_SCHEMA_ADAPTER",
                "autoConfirmed": True, "candidateSource": "PRECOMPILED_SCHEMA",
                "reason": "预编译网络结构签名已匹配；控制字段、标准财务字段和数值指标按确定性规则注册",
                "evidence": list(dict.fromkeys([*(item.get("evidence") or []), "PRECOMPILED_NETWORK_SCHEMA_SIGNATURE"])),
            })
            confirmed += 1
        else:
            unresolved += 1
    return {
        "detected": True, "tables": sorted(str(item) for item in tables), "adapterModes": modes,
        "autoConfirmed": confirmed, "needsReview": unresolved,
        "status": "SCHEMA_CONFIRMED_JSON_PENDING_VALUE_VALIDATION",
    }


def _parts(source_field: str) -> tuple[str, str]:
    parts = source_field.split(".")
    if len(parts) < 2:
        return "data", parts[-1]
    return parts[-2], parts[-1]


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _compact_date(value: str) -> str:
    return re.sub(r"[^0-9]", "", value)[:8]


def _date_key(value: Any) -> str:
    return re.sub(r"[^0-9]", "", str(value or ""))[:8]


def _mapping_by_table(mappings: list[dict[str, Any]], default_schema: str, expected_database: str | None = None) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in mappings:
        if item.get("status") != "CONFIRMED" or not _metric_for_mapping(item):
            continue
        locator = item.get("sourceLocator") if isinstance(item.get("sourceLocator"), dict) else {}
        fallback_table, fallback_column = _parts(str(item.get("sourceField") or item.get("sourceColumn") or ""))
        mapped_database = str(locator.get("database") or item.get("databaseName") or "").strip()
        if expected_database and mapped_database and mapped_database != expected_database:
            raise ValueError(f"MAPPING_DATABASE_MISMATCH:{mapped_database}:{expected_database}")
        schema = safe_identifier(locator.get("schema") or item.get("schemaName") or default_schema, "schema")
        table = safe_identifier(locator.get("table") or item.get("tableName") or fallback_table, "table")
        virtual = item.get("valueMode") in {"CONSTANT", "SYNC_CUTOFF", "ROW_HASH"}
        column = None if virtual else safe_identifier(locator.get("column") or item.get("columnName") or fallback_column, "column")
        grouped.setdefault((schema, table), []).append({**item, "schema": schema, "table": table, "column": column})
    return grouped


def _row_values(rows: list[dict[str, Any]], mappings: list[dict[str, Any]], source_id: str, cutoff: str, snapshot_id: str, table: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    by_code = {item["metricCode"]: item for item in mappings}
    output: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    for row_index, row in enumerate(rows):
        def mapped_value(item: dict[str, Any]) -> Any:
            if item.get("valueMode") == "CONSTANT":
                return item.get("constantValue")
            if item.get("valueMode") == "SYNC_CUTOFF":
                return cutoff
            if item.get("valueMode") == "ROW_HASH":
                return stable_id("ROW", {"table": table, "values": row})
            return _scalar(row.get(item.get("column")))

        def dimension(code: str) -> Any:
            item = by_code.get(code)
            return mapped_value(item) if item else None
        entity = dimension("ENTITY_CODE")
        entity_name = dimension("ENTITY_NAME")
        # Some benchmark tables expose only the exchange (SH/SZ) as the code.
        # Combine it with the localized entity name so distinct companies are not collapsed.
        if entity and entity_name and str(entity).upper() in {"SH", "SZ", "HK", "US"}:
            entity = f"{entity}:{entity_name}"
        report_period = dimension("REPORT_PERIOD")
        announcement_items = [item for item in mappings if item["metricCode"] == "ANNOUNCEMENT_DATE"]
        announcement_items.sort(key=lambda item: 0 if str(item.get("column") or "").lower() == "actual_ann_dt" else 1)
        announcement = next((mapped_value(item) for item in announcement_items if mapped_value(item) not in (None, "")), None)
        cutoff_assumed = any(item.get("valueMode") == "SYNC_CUTOFF" for item in announcement_items)
        currency = dimension("CURRENCY")
        opdate = dimension("OPDATE")
        row_key = dimension("ROW_KEY") or f"{table}:{entity}:{report_period}:{row_index}"
        if not entity:
            rejected["ENTITY_CODE_MISSING"] = rejected.get("ENTITY_CODE_MISSING", 0) + 1
            continue
        if not report_period:
            rejected["REPORT_PERIOD_MISSING"] = rejected.get("REPORT_PERIOD_MISSING", 0) + 1
            continue
        if (announcement and _date_key(announcement) > _date_key(cutoff)) or (opdate and _date_key(opdate) > _date_key(cutoff)):
            rejected["AFTER_DATA_CUTOFF"] = rejected.get("AFTER_DATA_CUTOFF", 0) + 1
            continue
        for item in mappings:
            code = item["metricCode"]
            metric_def = _metric_for_mapping(item)
            if not metric_def:
                rejected["MAPPING_DEFINITION_MISSING:" + str(item.get("tableName") or table) + "." + str(item.get("columnName") or item.get("column") or "unknown")] = rejected.get("MAPPING_DEFINITION_MISSING:" + str(item.get("tableName") or table) + "." + str(item.get("columnName") or item.get("column") or "unknown"), 0) + 1
                continue
            if code in DIMENSION_CODES:
                continue
            if item.get("valueMode"):
                continue
            value = _scalar(row.get(item["column"]))
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            evidence_id = stable_id("EVD", {"snapshot": snapshot_id, "table": table, "row": row_key, "column": item["column"], "opdate": opdate})
            evidence.append({
                "evidenceId": evidence_id, "sourceId": source_id, "sourceSnapshotId": snapshot_id,
                "sourceTable": table, "sourceColumn": item["column"], "sourceRowKey": str(row_key),
                "reportPeriod": str(report_period), "announcementDate": str(announcement) if announcement else None,
                "opdate": str(opdate) if opdate else None, "dataCutoff": cutoff,
                "status": "DATABASE_CANDIDATE", "locator": f"{table}.{item['column']} / {row_key}",
                "temporalBasis": "SYNC_CUTOFF_ASSUMPTION" if cutoff_assumed else "SOURCE_ANNOUNCEMENT_DATE",
                "historicalReplayEligible": not cutoff_assumed,
            })
            output.append({
                "metricValueId": stable_id("MV", {"evidence": evidence_id, "metric": code}),
                "metricCode": code, "metricName": _metric_for_mapping(item)["metricName"], "metricType": _metric_for_mapping(item).get("metricType"), "networkLayer": _metric_for_mapping(item).get("networkLayer"), "metricDescription": _metric_for_mapping(item).get("description"), "semanticSource": _metric_for_mapping(item).get("semanticSource"), "semanticConfidence": item.get("semanticConfidence"), "semanticReason": item.get("reason"), "entityCode": str(entity),
                "entityName": str(entity_name) if entity_name else None,
                "value": value, "unit": _metric_for_mapping(item).get("unit"), "currency": str(currency) if currency else None,
                "reportPeriod": str(report_period), "announcementDate": str(announcement) if announcement else None,
                "dataCutoff": cutoff, "sourceId": source_id, "sourceTable": table, "sourceColumn": item["column"],
                "sourceRowKey": str(row_key), "valueStatus": _metric_for_mapping(item).get("valueStatus") or "REPORTED_ACTUAL", "evidenceId": evidence_id,
                "version": str(opdate or announcement or snapshot_id), "opdate": str(opdate) if opdate else None,
                "temporalBasis": "SYNC_CUTOFF_ASSUMPTION" if cutoff_assumed else "SOURCE_ANNOUNCEMENT_DATE",
                "historicalReplayEligible": not cutoff_assumed,
            })
    unique_evidence = {item["evidenceId"]: item for item in evidence}
    return output, list(unique_evidence.values()), rejected


def _json_document(value: Any, label: str) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    if len(text.encode("utf-8")) > 5 * 1024 * 1024:
        raise ValueError(f"PRECOMPILED_NETWORK_INVALID:{label}_TOO_LARGE")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"PRECOMPILED_NETWORK_INVALID:{label}_JSON:{exc.lineno}:{exc.colno}") from exc


def _extract_precompiled_network(rows: list[dict[str, Any]], mappings: list[dict[str, Any]], source_id: str, cutoff: str, table: str) -> dict[str, Any] | None:
    by_code = {item.get("metricCode"): item for item in mappings if item.get("column")}
    if not ((by_code.get("NETWORK_NODES_JSON") and by_code.get("NETWORK_EDGES_JSON")) or by_code.get("NETWORK_METADATA_JSON")):
        return None

    def value(row: dict[str, Any], code: str) -> Any:
        item = by_code.get(code)
        return row.get(item.get("column")) if item else None

    raw_nodes: list[Any] = []
    raw_edges: list[Any] = []
    raw_layers: list[Any] = []
    network_id = None
    network_name = None
    network_version = None
    for row in rows:
        metadata = _json_document(value(row, "NETWORK_METADATA_JSON"), "NETWORK_METADATA") or {}
        if not isinstance(metadata, dict):
            raise ValueError("PRECOMPILED_NETWORK_INVALID:NETWORK_METADATA_OBJECT_REQUIRED")
        node_doc = _json_document(value(row, "NETWORK_NODES_JSON"), "NODES")
        edge_doc = _json_document(value(row, "NETWORK_EDGES_JSON"), "EDGES")
        layer_doc = _json_document(value(row, "NETWORK_LAYERS_JSON"), "LAYERS")
        nodes = node_doc.get("nodes") if isinstance(node_doc, dict) else node_doc
        edges = edge_doc.get("edges") if isinstance(edge_doc, dict) else edge_doc
        layers = layer_doc.get("layers") if isinstance(layer_doc, dict) else layer_doc
        raw_nodes.extend(nodes or metadata.get("nodes") or [])
        raw_edges.extend(edges or metadata.get("edges") or [])
        raw_layers.extend(layers or metadata.get("layers") or metadata.get("layerLabels") or [])
        network_id = network_id or value(row, "NETWORK_ID") or metadata.get("networkId")
        network_name = network_name or value(row, "NETWORK_NAME") or metadata.get("networkName")
        network_version = network_version or value(row, "NETWORK_VERSION") or metadata.get("schemaVersion") or metadata.get("version")
    if not raw_nodes:
        raise ValueError("PRECOMPILED_NETWORK_INVALID:NODES_EMPTY")
    if not isinstance(raw_nodes, list) or len(raw_nodes) > 500:
        raise ValueError("PRECOMPILED_NETWORK_INVALID:NODE_LIMIT")
    if not isinstance(raw_edges, list) or len(raw_edges) > 3000:
        raise ValueError("PRECOMPILED_NETWORK_INVALID:EDGE_LIMIT")

    layer_aliases = {
        "macro": "macro", "source": "macro", "time": "macro", "数据范围": "macro", "时间": "macro",
        "demand": "demand", "market": "demand", "growth": "demand", "市场": "demand", "增长": "demand",
        "route": "route", "operations": "route", "efficiency": "route", "运营": "route", "效率": "route",
        "constraint": "constraint", "capital": "constraint", "risk": "constraint", "资本": "constraint", "风险": "constraint",
        "chain": "chain", "outcome": "chain", "quality": "chain", "结果": "chain", "质量": "chain",
        "company": "company", "entity": "company", "公司": "company", "实体": "company",
    }
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:NODE_OBJECT:{index}")
        node_id = str(raw.get("nodeId") or raw.get("id") or "").strip()
        layer = layer_aliases.get(str(raw.get("layer") or raw.get("level") or "").strip().lower())
        if not node_id or len(node_id) > 128 or not layer:
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:NODE_ID_OR_LAYER:{index}")
        baseline = raw.get("baseline") if isinstance(raw.get("baseline"), dict) else {}
        scalar = raw.get("baselineValue", raw.get("value"))
        if not baseline and isinstance(scalar, (int, float)) and not isinstance(scalar, bool):
            baseline = {str(raw.get("entityCode") or "BASE"): float(scalar)}
        metric_codes = raw.get("metricCodes") or ([raw.get("metricCode")] if raw.get("metricCode") else [])
        if isinstance(metric_codes, str):
            metric_codes = [metric_codes]
        nodes_by_id[node_id] = {
            "nodeId": node_id, "layer": layer, "layerNo": int(raw.get("layerNo") or raw.get("layer_no") or 0) or None, "nodeType": raw.get("nodeType"), "label": str(raw.get("label") or raw.get("name") or node_id)[:120],
            "sub": str(raw.get("sub") or raw.get("subtitle") or raw.get("entityCode") or "")[:120],
            "description": str(raw.get("description") or raw.get("meaning") or "预编译网络节点")[:500],
            "unit": raw.get("unit"), "entityCode": raw.get("entityCode"), "metricCodes": [str(item) for item in metric_codes if item],
            "baseline": baseline, "evidenceIds": [str(item) for item in (raw.get("evidenceIds") or [])],
            "status": str(raw.get("status") or "CONFIRMED_DATA"), "source": "PRECOMPILED_NETWORK_TABLE",
            "companyModel": raw.get("companyModel"),
        }
    edges_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:EDGE_OBJECT:{index}")
        source = str(raw.get("sourceNodeId") or raw.get("source") or raw.get("from") or "").strip()
        target = str(raw.get("targetNodeId") or raw.get("target") or raw.get("to") or "").strip()
        if source not in nodes_by_id or target not in nodes_by_id:
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:EDGE_ENDPOINT:{index}")
        direction = str(raw.get("direction") or "mixed").lower()
        if direction not in {"positive", "negative", "mixed"}:
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:EDGE_DIRECTION:{index}")
        weight = float(raw.get("weight") or 0)
        lag_days = int(raw.get("lagDays") or raw.get("lag_days") or 0)
        confidence = float(raw.get("confidence") or 0)
        if not 0 <= weight <= 3 or not 0 <= lag_days <= 3650 or not 0 <= confidence <= 1:
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:EDGE_PARAMETER:{index}")
        mechanism = str(raw.get("mechanism") or "").strip()
        evidence_source = raw.get("evidenceSource") or raw.get("evidence")
        requested_status = str(raw.get("status") or "CANDIDATE").upper()
        structural = str(raw.get("relationType") or "").upper() in {"DATA_LINEAGE", "ENTITY_METRIC", "ACCOUNTING_STRUCTURE"}
        source_formula_type = str(raw.get("formulaType") or "LINEAR_WEIGHT").strip().upper()
        formula_type, formula_resolution = normalize_formula_type(source_formula_type, raw.get("formulaExpression"))
        formula_supported = formula_type in SUPPORTED_FORMULAS
        confirmed = requested_status.startswith("CONFIRMED") and formula_supported and (structural or (mechanism and evidence_source and weight > 0 and direction != "mixed"))
        status = requested_status if confirmed else "CANDIDATE"
        edge_id = str(raw.get("edgeId") or raw.get("id") or stable_id("EDGE", {"source": source, "target": target, "index": index}))
        edges_by_id[edge_id] = {
            "edgeId": edge_id, "sourceNodeId": source, "targetNodeId": target, "direction": direction,
            "weight": weight, "lagDays": lag_days, "confidence": confidence, "mechanism": mechanism or "机制说明待审核",
            "evidenceSource": evidence_source or "MISSING", "status": status,
            "relationType": str(raw.get("relationType") or "PRECOMPILED_SCENARIO_EDGE"),
            "formulaType": formula_type or "FORMULA_NEEDS_REVIEW",
            "sourceFormulaType": source_formula_type,
            "formulaResolution": formula_resolution,
            "formulaSupported": formula_supported,
            "formulaParameters": raw.get("formulaParameters") if isinstance(raw.get("formulaParameters"), dict) else {},
            "candidateWeight": (abs(weight) if weight else min(0.6, max(0.1, confidence * 0.5))) if formula_supported and not confirmed else 0.0,
            "candidateSimulation": bool(formula_supported and not confirmed),
        }
    layers = []
    for raw in raw_layers:
        if not isinstance(raw, dict):
            continue
        layer_id = layer_aliases.get(str(raw.get("id") or raw.get("layer") or "").strip().lower())
        if layer_id and not any(item["id"] == layer_id for item in layers):
            layers.append({"id": layer_id, "label": str(raw.get("label") or layer_id), "subtitle": str(raw.get("subtitle") or "PRECOMPILED")})
    return {
        "networkId": str(network_id or stable_id("NETWORK", {"source": source_id, "table": table}))[:128],
        "networkName": str(network_name or table)[:120], "schemaVersion": str(network_version or "1.0")[:40],
        "nodes": list(nodes_by_id.values()), "edges": list(edges_by_id.values()),
        "layerLabels": layers or SOURCE_DEFINED_LAYER_LABELS, "sourceTable": table, "dataCutoff": cutoff,
        "validationStatus": "VALIDATED", "nodeCount": len(nodes_by_id), "edgeCount": len(edges_by_id),
    }


def _controls(mappings: list[dict[str, Any]]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for item in mappings:
        if item.get("column"):
            output.setdefault(item["metricCode"], []).append(item["column"])
    output["ANNOUNCEMENT_DATE"] = sorted(output.get("ANNOUNCEMENT_DATE", []), key=lambda name: 0 if name.lower() == "actual_ann_dt" else 1)
    return output


def _extract_columnar_precompiled_controls(rows: list[dict[str, Any]], mappings: list[dict[str, Any]], table: str) -> dict[str, Any] | None:
    by_code = {item.get("metricCode"): item for item in mappings if item.get("column")}
    required = {"NETWORK_EDITABLE_METRIC_NAME", "NETWORK_EDITABLE_BASELINE_VALUE", "NETWORK_DRIVER_SENSITIVITY", "NETWORK_LAG_DAYS", "NETWORK_IMPACT_CAP_PCT"}
    if not required.issubset(by_code):
        return None

    def raw(row: dict[str, Any], code: str) -> Any:
        item = by_code.get(code)
        return row.get(item.get("column")) if item else None

    def number(value: Any, label: str, minimum: float, maximum: float) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:{label}_NUMBER") from exc
        if not math.isfinite(result) or result < minimum or result > maximum:
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:{label}_RANGE")
        return result

    controls = []
    for index, row in enumerate(rows):
        entity = str(raw(row, "ENTITY_CODE") or "").strip()
        entity_name_value = str(raw(row, "ENTITY_NAME") or "").strip()
        metric_name = str(raw(row, "NETWORK_EDITABLE_METRIC_NAME") or "").strip()
        if entity_name_value and entity.upper() in {"SH", "SZ", "HK", "US"}:
            entity = f"{entity}:{entity_name_value}"
        if not entity or not metric_name:
            raise ValueError(f"PRECOMPILED_NETWORK_INVALID:COLUMNAR_ENTITY_OR_EDITABLE_METRIC:{index}")
        sensitivity = number(raw(row, "NETWORK_DRIVER_SENSITIVITY"), f"DRIVER_SENSITIVITY:{index}", -3, 3)
        direction_value = str(raw(row, "NETWORK_DRIVER_DIRECTION") or "").strip().lower()
        direction_aliases = {"+": "positive", "正向": "positive", "positive": "positive", "-": "negative", "负向": "negative", "negative": "negative"}
        direction = direction_aliases.get(direction_value, "negative" if sensitivity < 0 else "positive")
        controls.append({
            "entityCode": entity,
            "entityName": entity_name_value or None,
            "chainLayerNo": raw(row, "NETWORK_CHAIN_LAYER_NO"),
            "chainLayerName": str(raw(row, "NETWORK_CHAIN_LAYER_NAME") or "").strip() or None,
            "chainPosition": str(raw(row, "NETWORK_CHAIN_POSITION") or "").strip() or None,
            "editableMetricCode": str(raw(row, "NETWORK_EDITABLE_METRIC_CODE") or "").strip() or None,
            "editableMetricName": metric_name,
            "editableMetricType": str(raw(row, "NETWORK_EDITABLE_METRIC_TYPE") or "index").strip().lower(),
            "editableMetricUnit": str(raw(row, "NETWORK_EDITABLE_METRIC_UNIT") or "%").strip(),
            "editableBaselineValue": number(raw(row, "NETWORK_EDITABLE_BASELINE_VALUE"), f"EDITABLE_BASELINE:{index}", -1e18, 1e18),
            "driverSensitivity": sensitivity,
            "direction": direction,
            "lagDays": int(number(raw(row, "NETWORK_LAG_DAYS"), f"LAG_DAYS:{index}", 0, 3650)),
            "impactCapPct": number(raw(row, "NETWORK_IMPACT_CAP_PCT"), f"IMPACT_CAP_PCT:{index}", 0, 300),
            "mechanism": str(raw(row, "NETWORK_DRIVER_MECHANISM") or "").strip() or f"{metric_name}的情景变化按公司敏感度传导，并受影响上限约束。",
        })
    return {
        "adapterMode": "PRECOMPILED_NETWORK_COLUMNS", "sourceTable": table,
        "validationStatus": "VALIDATED", "rowCount": len(controls), "controls": controls,
    }


def _postgres_date_expression(columns: list[str]) -> sql.Composed:
    values = sql.SQL(", ").join(sql.SQL("NULLIF(CAST({column} AS TEXT), '')").format(column=sql.Identifier(name)) for name in columns)
    return sql.SQL("LEFT(regexp_replace(COALESCE({values}, ''), '[^0-9]', '', 'g'), 8)").format(values=values)


def _role_for_mappings(mappings: list[dict[str, Any]]) -> str:
    declared = [str(item.get("tableRole") or "") for item in mappings if str(item.get("tableRole") or "") not in {"", "UNKNOWN"}]
    if declared:
        return max(set(declared), key=declared.count)
    codes = {str(item.get("metricCode") or "") for item in mappings}
    if "NETWORK_NODE_ID" in codes: return "NODES"
    if "NETWORK_EDGE_SOURCE" in codes: return "EDGES"
    if "NETWORK_LAYER_NO" in codes: return "LAYERS"
    if "FORMULA_ID" in codes and "FORMULA_TYPE" in codes: return "FORMULAS"
    if "EVIDENCE_ID" in codes and codes.intersection({"EVIDENCE_QUOTE", "EVIDENCE_URL"}): return "EVIDENCE"
    if "METRIC_CODE" in codes and "METRIC_VALUE" in codes: return "METRIC_VALUES"
    if "VALUATION_DATE" in codes: return "VALUATION"
    if "ENTITY_CODE" in codes and "REPORT_PERIOD" in codes: return "FINANCIALS"
    if codes.intersection({"NETWORK_ID", "NETWORK_NAME", "NETWORK_STATUS"}) and "ENTITY_CODE" not in codes: return "REGISTRY"
    if "ENTITY_CODE" in codes: return "METRICS"
    return "UNKNOWN"

def _postgres_rows(config: dict[str, Any], schema: str, table: str, mappings: list[dict[str, Any]], cutoff: str, entity_codes: list[str], limit: int, offset: int) -> list[dict[str, Any]]:
    schema, table = safe_identifier(schema, "schema"), safe_identifier(table, "table")
    columns = list(dict.fromkeys(item["column"] for item in mappings if item.get("column")))
    controls = _controls(mappings)
    entity_mapping = next((item for item in mappings if item["metricCode"] == "ENTITY_CODE"), None)
    virtual_entity = bool(entity_mapping and entity_mapping.get("valueMode") == "ROW_HASH")
    report_mapping = next((item for item in mappings if item.get("metricCode") == "REPORT_PERIOD"), {})
    precompiled = bool((controls.get("NETWORK_NODES_JSON") and controls.get("NETWORK_EDGES_JSON")) or controls.get("NETWORK_METADATA_JSON"))
    role = _role_for_mappings(mappings)
    direct_role = role in STRUCTURAL_ROLES | {"METRIC_VALUES", "CALCULATED_LINEAGE", "VALUATION"}
    if not precompiled and not direct_role and ((not controls.get("ENTITY_CODE") and not virtual_entity) or not report_mapping):
        raise ValueError(f"CONFIRMED_CONTROL_FIELDS_REQUIRED:{table}:ENTITY_OR_ROW_ID,REPORT_PERIOD")
    if not precompiled and not direct_role and not controls.get("ANNOUNCEMENT_DATE") and not controls.get("OPDATE") and not any(item.get("metricCode") == "ANNOUNCEMENT_DATE" and item.get("valueMode") == "SYNC_CUTOFF" for item in mappings):
        raise ValueError(f"CUTOFF_MAPPING_REQUIRED:{table}:ANNOUNCEMENT_DATE_OR_OPDATE")
    entity_column = controls["ENTITY_CODE"][0] if controls.get("ENTITY_CODE") else None
    report_expression = sql.Identifier(controls["REPORT_PERIOD"][0]) if controls.get("REPORT_PERIOD") else sql.Literal(report_mapping.get("constantValue") if report_mapping else cutoff)
    select_columns = sql.SQL(", ").join(sql.Identifier(name) for name in columns)
    filters: list[Any] = []
    params: list[Any] = []
    if table.lower() in {"asharebalancesheet", "asharecashflow", "ashareincome"} and controls.get("STATEMENT_TYPE"):
        filters.append(sql.SQL("CAST({column} AS TEXT) = %s").format(column=sql.Identifier(controls["STATEMENT_TYPE"][0])))
        params.append("408001000")
    cutoff_codes = ["ANNOUNCEMENT_DATE", "OPDATE"]
    if role == "METRIC_VALUES":
        cutoff_codes.insert(0, "AS_OF_DATE")
    elif role == "VALUATION":
        cutoff_codes = ["VALUATION_DATE", "AS_OF_DATE", *cutoff_codes]
    for code in cutoff_codes:
        if controls.get(code):
            filters.append(sql.SQL("{date_value} <= %s").format(date_value=_postgres_date_expression(controls[code])))
            params.append(_compact_date(cutoff))
    if entity_codes and entity_column:
        filters.append(sql.SQL("CAST({column} AS TEXT) = ANY(%s)").format(column=sql.Identifier(entity_column)))
        params.append(entity_codes)
    order_parts = [_postgres_date_expression(controls[code]) for code in cutoff_codes if controls.get(code)]
    order_sql = sql.SQL(" DESC, ").join(order_parts) + sql.SQL(" DESC") if order_parts else (sql.Identifier(entity_column) if entity_column else sql.Identifier(columns[0]))
    if precompiled or direct_role or virtual_entity:
        query = sql.SQL("""
            SELECT {columns} FROM {schema}.{table}
            WHERE {filters}
            ORDER BY {version_order}
            LIMIT %s OFFSET %s
        """).format(
            columns=select_columns, schema=sql.Identifier(schema), table=sql.Identifier(table),
            filters=sql.SQL(" AND ").join(filters) if filters else sql.SQL("TRUE"), version_order=order_sql,
        )
    else:
        query = sql.SQL("""
        SELECT {columns} FROM (
          SELECT {columns}, ROW_NUMBER() OVER (
            PARTITION BY {entity}, {report}
            ORDER BY {version_order}
          ) AS __nexus_row_number
          FROM {schema}.{table}
          WHERE {filters}
        ) AS visible WHERE __nexus_row_number = 1
        ORDER BY {report} DESC, {entity}
        LIMIT %s OFFSET %s
        """).format(
            columns=select_columns, entity=sql.Identifier(entity_column), report=report_expression,
            version_order=order_sql, schema=sql.Identifier(schema), table=sql.Identifier(table),
            filters=sql.SQL(" AND ").join(filters) if filters else sql.SQL("TRUE"),
        )
    params.extend([limit, offset])
    connection = {key: config.get(key) for key in ("host", "port", "user", "sslmode") if config.get(key) not in (None, "")}
    password = _database_password(config)
    if password is not None:
        connection["password"] = password
    connection["dbname"] = config.get("database") or config.get("dbname")
    connection["connect_timeout"] = 8
    connection["options"] = "-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=5000"
    with psycopg.connect(**connection) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        if conn.execute("SHOW transaction_read_only").fetchone()[0] != "on":
            raise RuntimeError("READ_ONLY_GUARD_FAILED")
        cursor = conn.execute(query, params)
        names = [item.name for item in cursor.description]
        rows = [dict(zip(names, row)) for row in cursor.fetchall()]
        conn.rollback()
    return rows


def _mysql_identifier(value: Any, key: str) -> str:
    quote = chr(96)
    return quote + safe_identifier(value, key).replace(quote, quote + quote).replace("%", "%%") + quote


def _mysql_date_expression(columns: list[str]) -> str:
    values = ", ".join("NULLIF(CAST(" + _mysql_identifier(name, "column") + " AS CHAR), '')" for name in columns)
    return "LEFT(REGEXP_REPLACE(COALESCE(" + values + ", ''), '[^0-9]', ''), 8)"


def _mysql_rows(config: dict[str, Any], schema: str, table: str, mappings: list[dict[str, Any]], cutoff: str, entity_codes: list[str], limit: int, offset: int) -> list[dict[str, Any]]:
    schema, table = safe_identifier(schema, "schema"), safe_identifier(table, "table")
    columns = list(dict.fromkeys(item["column"] for item in mappings if item.get("column")))
    controls = _controls(mappings)
    entity_mapping = next((item for item in mappings if item["metricCode"] == "ENTITY_CODE"), None)
    virtual_entity = bool(entity_mapping and entity_mapping.get("valueMode") == "ROW_HASH")
    report_mapping = next((item for item in mappings if item.get("metricCode") == "REPORT_PERIOD"), {})
    precompiled = bool((controls.get("NETWORK_NODES_JSON") and controls.get("NETWORK_EDGES_JSON")) or controls.get("NETWORK_METADATA_JSON"))
    role = _role_for_mappings(mappings)
    direct_role = role in STRUCTURAL_ROLES | {"METRIC_VALUES", "CALCULATED_LINEAGE", "VALUATION"}
    if not precompiled and not direct_role and ((not controls.get("ENTITY_CODE") and not virtual_entity) or not report_mapping):
        raise ValueError(f"CONFIRMED_CONTROL_FIELDS_REQUIRED:{table}:ENTITY_OR_ROW_ID,REPORT_PERIOD")
    if not precompiled and not direct_role and not controls.get("ANNOUNCEMENT_DATE") and not controls.get("OPDATE") and not any(item.get("metricCode") == "ANNOUNCEMENT_DATE" and item.get("valueMode") == "SYNC_CUTOFF" for item in mappings):
        raise ValueError(f"CUTOFF_MAPPING_REQUIRED:{table}:ANNOUNCEMENT_DATE_OR_OPDATE")
    entity_column = controls["ENTITY_CODE"][0] if controls.get("ENTITY_CODE") else None
    report_expression = _mysql_identifier(controls["REPORT_PERIOD"][0], "column") if controls.get("REPORT_PERIOD") else "%s"
    quoted = ", ".join(_mysql_identifier(name, "column") for name in columns)
    filters: list[str] = []
    params: list[Any] = []
    if table.lower() in {"asharebalancesheet", "asharecashflow", "ashareincome"} and controls.get("STATEMENT_TYPE"):
        filters.append("CAST(" + _mysql_identifier(controls["STATEMENT_TYPE"][0], "column") + " AS CHAR) = %s")
        params.append("408001000")
    cutoff_codes = ["ANNOUNCEMENT_DATE", "OPDATE"]
    if role == "METRIC_VALUES":
        cutoff_codes.insert(0, "AS_OF_DATE")
    elif role == "VALUATION":
        cutoff_codes = ["VALUATION_DATE", "AS_OF_DATE", *cutoff_codes]
    for code in cutoff_codes:
        if controls.get(code):
            filters.append(_mysql_date_expression(controls[code]) + " <= %s")
            params.append(_compact_date(cutoff))
    if entity_codes and entity_column:
        filters.append("CAST(" + _mysql_identifier(entity_column, "column") + " AS CHAR) IN (" + ",".join(["%s"] * len(entity_codes)) + ")")
        params.extend(entity_codes)
    order_parts = [_mysql_date_expression(controls[code]) for code in cutoff_codes if controls.get(code)]
    order_sql = " DESC, ".join(order_parts) + " DESC" if order_parts else (_mysql_identifier(entity_column, "column") if entity_column else _mysql_identifier(columns[0], "column"))
    if precompiled or direct_role or virtual_entity:
        query = "SELECT " + quoted + " FROM " + _mysql_identifier(schema, "schema") + "." + _mysql_identifier(table, "table") + " WHERE " + (" AND ".join(filters) if filters else "1=1") + " ORDER BY " + order_sql + " LIMIT %s OFFSET %s"
    else:
        query = "SELECT " + quoted + " FROM (SELECT " + quoted + ", ROW_NUMBER() OVER (PARTITION BY " + _mysql_identifier(entity_column, "column") + ", " + report_expression + " ORDER BY " + order_sql + ") AS __nexus_row_number FROM " + _mysql_identifier(schema, "schema") + "." + _mysql_identifier(table, "table") + " WHERE " + (" AND ".join(filters) if filters else "1=1") + ") AS visible WHERE __nexus_row_number=1 ORDER BY " + report_expression + " DESC, " + _mysql_identifier(entity_column, "column") + " LIMIT %s OFFSET %s"
    if not precompiled and not direct_role and not virtual_entity and not controls.get("REPORT_PERIOD"): 
        report_constant = (report_mapping or {}).get("constantValue") or cutoff
        params = [report_constant, *params, report_constant]
    params.extend([limit, offset])
    sslmode = str(config.get("sslmode") or "preferred")
    conn = pymysql.connect(host=config["host"], port=int(config.get("port") or 3306), database=config["database"], user=config["user"], password=_database_password(config), connect_timeout=8, read_timeout=30, write_timeout=5, autocommit=False, charset="utf8mb4", ssl=None if sslmode == "disabled" else {})
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute(query, params)
            rows = list(cursor.fetchall())
        conn.rollback()
    finally:
        conn.close()
    return rows


def _mapped_value(row: dict[str, Any], mappings: list[dict[str, Any]], *codes: str) -> Any:
    for code in codes:
        item = next((mapping for mapping in mappings if mapping.get("metricCode") == code), None)
        if not item:
            continue
        mode = item.get("valueMode")
        if mode == "CONSTANT":
            return item.get("constantValue")
        column = item.get("column")
        if column is not None:
            return row.get(column)
    return None


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def _baseline(value: Any) -> dict[str, float]:
    if isinstance(value, dict):
        return {str(key): _numeric(item) for key, item in value.items() if item not in (None, "")}
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(value)) if isinstance(value, str) else value
        if isinstance(parsed, dict):
            return {str(key): _numeric(item) for key, item in parsed.items() if item not in (None, "")}
        return {"BASE": float(parsed)}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _extract_multi_table_network(
    role_rows: list[tuple[str, list[dict[str, Any]], list[dict[str, Any]], str]],
    source_id: str,
    cutoff: str,
) -> list[dict[str, Any]]:
    if not any(role == "NODES" for role, *_ in role_rows):
        return []

    registry_ids = {
        str(_mapped_value(row, mappings, "NETWORK_ID") or "").strip()
        for role, rows, mappings, _ in role_rows if role == "REGISTRY"
        for row in rows
        if str(_mapped_value(row, mappings, "NETWORK_ID") or "").strip()
    }
    core_ids = {
        str(_mapped_value(row, mappings, "NETWORK_ID") or "").strip()
        for role, rows, mappings, _ in role_rows if role in {"LAYERS", "NODES", "EDGES", "FORMULAS"}
        for row in rows
        if str(_mapped_value(row, mappings, "NETWORK_ID") or "").strip()
    }
    network_ids = sorted(core_ids | registry_ids)
    if not network_ids:
        return []

    definitions: list[dict[str, Any]] = []
    for network_id in network_ids:
        entries: list[tuple[str, dict[str, Any], list[dict[str, Any]], str]] = []
        for role, rows, mappings, table in role_rows:
            for row in rows:
                row_network = str(_mapped_value(row, mappings, "NETWORK_ID") or "").strip()
                if row_network == network_id or (not row_network and role in {"EVIDENCE", "FINANCIALS", "VALUATION", "METRICS"}):
                    entries.append((role, row, mappings, table))

        issues: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        registry = next(((row, mappings) for role, row, mappings, _ in entries if role == "REGISTRY"), None)
        network_name = str(_mapped_value(registry[0], registry[1], "NETWORK_NAME") or "").strip() if registry else ""
        network_version = str(_mapped_value(registry[0], registry[1], "NETWORK_VERSION") or "").strip() if registry else ""

        layer_records: list[dict[str, Any]] = []
        seen_layer_numbers: set[int] = set()
        for role, row, mappings, table in entries:
            if role != "LAYERS":
                continue
            raw_number = _mapped_value(row, mappings, "NETWORK_LAYER_NO", "NETWORK_NODE_LAYER")
            try:
                layer_no = int(float(raw_number))
            except (TypeError, ValueError):
                issues.append({"code": "INVALID_LAYER_NUMBER", "table": table, "value": raw_number})
                continue
            if not 1 <= layer_no <= 6:
                issues.append({"code": "INVALID_LAYER_NUMBER", "table": table, "value": raw_number})
                continue
            if layer_no in seen_layer_numbers:
                issues.append({"code": "DUPLICATE_LAYER_NUMBER", "table": table, "layerNo": layer_no})
                continue
            seen_layer_numbers.add(layer_no)
            code = str(_mapped_value(row, mappings, "NETWORK_LAYER_CODE") or f"layer-{layer_no}").strip()
            name = str(_mapped_value(row, mappings, "NETWORK_LAYER_NAME") or f"第 {layer_no} 层").strip()
            subtitle = str(_mapped_value(row, mappings, "NETWORK_LAYER_SUBTITLE") or "IMPORTED LAYER").strip()
            layer_records.append({"id": code, "code": code, "layerNo": layer_no, "label": name, "subtitle": subtitle, "sortOrder": _numeric(_mapped_value(row, mappings, "NETWORK_LAYER_SORT"), layer_no)})
        layer_records.sort(key=lambda item: (item["sortOrder"], item["layerNo"]))
        if not layer_records:
            issues.append({"code": "NO_VALID_LAYERS"})
            layer_records = [{"id": f"layer-{number}", "code": f"layer-{number}", "layerNo": number, "label": f"第 {number} 层", "subtitle": "IMPORTED LAYER", "sortOrder": number} for number in range(1, 7)]
        elif len(layer_records) != 6:
            missing_numbers = [number for number in range(1, 7) if number not in seen_layer_numbers]
            warnings.append({"code": "LAYER_COUNT_NOT_SIX", "missingLayerNumbers": missing_numbers})
            for number in missing_numbers:
                layer_records.append({"id": f"layer-{number}", "code": f"layer-{number}", "layerNo": number, "label": f"第 {number} 层", "subtitle": "待补充层定义", "sortOrder": number})
            layer_records.sort(key=lambda item: item["layerNo"])
        layer_no_by_token: dict[str, int] = {}
        for layer in layer_records:
            layer_no_by_token[str(layer["layerNo"])] = layer["layerNo"]
            layer_no_by_token[str(layer["code"]).strip().lower()] = layer["layerNo"]
            layer_no_by_token[str(layer["label"]).strip().lower()] = layer["layerNo"]

        formulas: dict[str, dict[str, Any]] = {}
        for role, row, mappings, table in entries:
            if role != "FORMULAS":
                continue
            formula_id = str(_mapped_value(row, mappings, "FORMULA_ID") or "").strip()
            source_formula_type = str(_mapped_value(row, mappings, "FORMULA_TYPE") or "").strip().upper()
            formula_expression = str(_mapped_value(row, mappings, "FORMULA_EXPRESSION") or "").strip()
            formula_type, formula_resolution = normalize_formula_type(source_formula_type, formula_expression)
            if not formula_id:
                continue
            parameters_valid = True
            try:
                parameters = parse_json_object(_mapped_value(row, mappings, "FORMULA_PARAMETERS"))
            except (ValueError, json.JSONDecodeError):
                parameters = {}
                parameters_valid = False
                warnings.append({"code": "FORMULA_PARAMETERS_QUARANTINED", "table": table, "formulaId": formula_id})
            if formula_type is None:
                warnings.append({"code": "FORMULA_NEEDS_REVIEW", "table": table, "formulaId": formula_id, "sourceFormulaType": source_formula_type})
            formulas[formula_id] = {
                "formulaId": formula_id, "formulaType": formula_type or "FORMULA_NEEDS_REVIEW",
                "sourceFormulaType": source_formula_type, "formulaExpression": formula_expression,
                "formulaResolution": formula_resolution,
                "formulaSupported": bool(formula_type in SUPPORTED_FORMULAS and parameters_valid),
                "parameters": parameters,
                "version": str(_mapped_value(row, mappings, "FORMULA_VERSION") or "1.0").strip(),
                "invalidation": str(_mapped_value(row, mappings, "FORMULA_INVALIDATION") or "").strip() or None,
            }

        nodes: list[dict[str, Any]] = []
        node_ids: set[str] = set()
        for role, row, mappings, table in entries:
            if role != "NODES":
                continue
            node_id = str(_mapped_value(row, mappings, "NETWORK_NODE_ID") or "").strip()
            raw_layer = _mapped_value(row, mappings, "NETWORK_NODE_LAYER")
            token = str(raw_layer or "").strip().lower()
            layer_no = layer_no_by_token.get(token)
            if not node_id:
                issues.append({"code": "NODE_ID_MISSING", "table": table})
                continue
            if node_id in node_ids:
                issues.append({"code": "DUPLICATE_NODE_ID", "table": table, "nodeId": node_id})
                continue
            if layer_no is None:
                issues.append({"code": "NODE_LAYER_INVALID", "table": table, "nodeId": node_id, "value": raw_layer})
                continue
            node_ids.add(node_id)
            layer = next(item for item in layer_records if item["layerNo"] == layer_no)
            editable_raw = _mapped_value(row, mappings, "NETWORK_NODE_EDITABLE")
            editable = str(editable_raw or "").strip().lower() in {"1", "true", "yes", "y", "是", "可调"}
            metric_code = str(_mapped_value(row, mappings, "NETWORK_NODE_METRIC_CODE") or "").strip() or None
            metric_name = str(_mapped_value(row, mappings, "NETWORK_NODE_METRIC_NAME") or "").strip() or None
            entity_code = _mapped_value(row, mappings, "ENTITY_CODE")
            evidence_id = _mapped_value(row, mappings, "EVIDENCE_ID")
            nodes.append({
                "nodeId": node_id, "layer": layer["code"], "layerNo": layer_no,
                "label": str(_mapped_value(row, mappings, "NETWORK_NODE_LABEL", "ENTITY_NAME") or node_id).strip(),
                "sub": metric_name or str(_mapped_value(row, mappings, "NETWORK_NODE_DESCRIPTION") or "").strip(),
                "description": str(_mapped_value(row, mappings, "NETWORK_NODE_DESCRIPTION") or "").strip() or None,
                "entityCode": str(entity_code).strip() if entity_code not in (None, "") else None,
                "metricCodes": [metric_code] if metric_code else [],
                "baseline": _baseline(_mapped_value(row, mappings, "NETWORK_NODE_BASELINE")),
                "editableDefinition": editable, "editable": editable,
                "unit": str(_mapped_value(row, mappings, "NETWORK_NODE_UNIT") or "").strip() or None,
                "valueStatus": str(_mapped_value(row, mappings, "NETWORK_NODE_VALUE_STATUS") or "").strip() or None,
                "nodeType": str(_mapped_value(row, mappings, "NETWORK_NODE_TYPE") or ("ENTITY" if entity_code else "METRIC")).strip(),
                "evidenceIds": [str(evidence_id)] if evidence_id else [],
                "status": "CONFIRMED_DATA", "sourceTable": table,
            })
        if not nodes:
            issues.append({"code": "NO_VALID_NODES"})

        nodes_by_id = {item["nodeId"]: item for item in nodes}
        nodes_by_entity = {item["entityCode"]: item for item in nodes if item.get("entityCode")}
        nodes_by_metric = {code: item for item in nodes for code in item.get("metricCodes", [])}
        evidence_records: list[dict[str, Any]] = []
        evidence_ids: set[str] = set()
        for role, row, mappings, table in entries:
            if role == "EVIDENCE":
                evidence_id = str(_mapped_value(row, mappings, "EVIDENCE_ID") or "").strip()
                if not evidence_id:
                    continue
                evidence_ids.add(evidence_id)
                evidence_records.append({
                    "evidenceId": evidence_id,
                    "quote": _mapped_value(row, mappings, "EVIDENCE_QUOTE"),
                    "url": _mapped_value(row, mappings, "EVIDENCE_URL"),
                    "sourceTable": table,
                })
            elif role == "METRIC_VALUES":
                metric_code = str(_mapped_value(row, mappings, "METRIC_CODE", "NETWORK_NODE_METRIC_CODE") or "").strip()
                value = _mapped_value(row, mappings, "METRIC_VALUE", "NETWORK_NODE_BASELINE")
                target_id = str(_mapped_value(row, mappings, "NETWORK_NODE_ID") or "").strip()
                entity_code = str(_mapped_value(row, mappings, "ENTITY_CODE") or "").strip()
                target = nodes_by_id.get(target_id) or nodes_by_entity.get(entity_code) or nodes_by_metric.get(metric_code)
                if not target or value in (None, ""):
                    warnings.append({"code": "METRIC_VALUE_UNATTACHED", "table": table, "metricCode": metric_code, "nodeId": target_id or None})
                    continue
                target.setdefault("baseline", {})[metric_code or "BASE"] = _numeric(value)
                if metric_code and metric_code not in target.setdefault("metricCodes", []):
                    target["metricCodes"].append(metric_code)
                target["dataCutoff"] = str(_mapped_value(row, mappings, "AS_OF_DATE", "REPORT_PERIOD") or cutoff)
            elif role in {"FINANCIALS", "VALUATION", "METRICS"}:
                entity_code = str(_mapped_value(row, mappings, "ENTITY_CODE") or "").strip()
                target = nodes_by_entity.get(entity_code)
                if not target:
                    continue
                for mapping in mappings:
                    code = str(mapping.get("metricCode") or "")
                    if code in DIMENSION_CODES or code.startswith("NETWORK_") or code in {"FORMULA_ID", "FORMULA_TYPE", "FORMULA_PARAMETERS", "FORMULA_VERSION", "FORMULA_INVALIDATION"}:
                        continue
                    value = row.get(mapping.get("column")) if mapping.get("column") is not None else None
                    if value not in (None, ""):
                        target.setdefault("baseline", {})[code] = _numeric(value)

        edges: list[dict[str, Any]] = []
        confirmed_statuses = {"CONFIRMED", "ACTIVE", "APPROVED", "CALIBRATED_PARAMETER", "ANALYST_ASSUMPTION"}
        candidate_statuses = {"AI_APPROVED", "CANDIDATE", "NEEDS_HUMAN_REVIEW"}
        structural_types = {"DATA_LINEAGE", "ENTITY_METRIC", "ACCOUNTING_STRUCTURE"}
        for index, (role, row, mappings, table) in enumerate(entries):
            if role != "EDGES":
                continue
            source = str(_mapped_value(row, mappings, "NETWORK_EDGE_SOURCE") or "").strip()
            target = str(_mapped_value(row, mappings, "NETWORK_EDGE_TARGET") or "").strip()
            if source not in node_ids or target not in node_ids:
                issues.append({"code": "EDGE_NODE_NOT_FOUND", "table": table, "sourceNodeId": source, "targetNodeId": target})
                continue
            formula_id = str(_mapped_value(row, mappings, "FORMULA_ID") or "").strip() or None
            declared_formula_type = str(_mapped_value(row, mappings, "FORMULA_TYPE") or "").strip().upper()
            formula = formulas.get(formula_id) if formula_id else None
            normalized_declared, declared_resolution = normalize_formula_type(declared_formula_type)
            formula_type = (formula or {}).get("formulaType") or normalized_declared or "FORMULA_NEEDS_REVIEW"
            formula_supported = bool(
                (formula or {}).get("formulaSupported", formula_type in SUPPORTED_FORMULAS)
                and formula_type in SUPPORTED_FORMULAS
            )
            edge_parameters_valid = True
            try:
                edge_parameters = parse_json_object(_mapped_value(row, mappings, "FORMULA_PARAMETERS"))
            except (ValueError, json.JSONDecodeError):
                edge_parameters = {}
                edge_parameters_valid = False
                warnings.append({"code": "EDGE_PARAMETERS_QUARANTINED", "table": table, "sourceNodeId": source, "targetNodeId": target})
            formula_supported = formula_supported and edge_parameters_valid
            parameters = {**((formula or {}).get("parameters") or {}), **edge_parameters}
            weight = _numeric(_mapped_value(row, mappings, "NETWORK_EDGE_WEIGHT"), _numeric(parameters.get("weight"), 0.0))
            source_status = str(_mapped_value(row, mappings, "NETWORK_EDGE_STATUS") or "").strip().upper()
            evidence = _mapped_value(row, mappings, "NETWORK_EDGE_EVIDENCE_SOURCE", "EVIDENCE_ID", "EVIDENCE_URL")
            requested_confirmed = source_status in confirmed_statuses or (not source_status and bool(evidence) and (weight != 0 or formula_id))
            confirmed = requested_confirmed and formula_supported
            edge_status = "CONFIRMED" if confirmed else "CANDIDATE"
            if confirmed and formula_id and not formula:
                issues.append({"code": "FORMULA_REFERENCE_NOT_FOUND", "table": table, "formulaId": formula_id, "sourceNodeId": source, "targetNodeId": target})
            if requested_confirmed and not formula_supported:
                warnings.append({"code": "EDGE_FORMULA_QUARANTINED", "table": table, "formulaType": formula_type, "sourceNodeId": source, "targetNodeId": target})
            relation_type = str(_mapped_value(row, mappings, "NETWORK_EDGE_RELATION_TYPE") or "CAUSAL").strip().upper()
            raw_direction = normalized_direction(_mapped_value(row, mappings, "NETWORK_EDGE_DIRECTION"))
            if raw_direction == "mixed":
                if formula_type == "SUBTRACT" and relation_type == "FORMULA_INPUT":
                    raw_direction = "negative"
                else:
                    raw_direction = "negative" if weight < 0 else ("positive" if weight > 0 else {
                    "COST_PRESSURE": "negative",
                    "OPERATING_TO_FINANCIAL": "positive",
                    "ACCOUNTING_STRUCTURE": "positive",
                    "VALUATION_BRIDGE": "positive",
                    "EXPOSURE": "positive",
                    }.get(relation_type, "positive"))
            confidence = max(0.0, min(1.0, _numeric(_mapped_value(row, mappings, "NETWORK_EDGE_CONFIDENCE"), 0)))
            candidate_eligible = formula_supported and (edge_status == "CANDIDATE" or source_status in candidate_statuses)
            candidate_weight = abs(weight) if candidate_eligible and abs(weight) > 0 else (min(0.6, max(0.1, confidence * 0.5)) if candidate_eligible else 0.0)
            edge_id = str(_mapped_value(row, mappings, "NETWORK_EDGE_ID") or "").strip() or stable_id("EDGE", {"network": network_id, "source": source, "target": target, "index": index})
            edges.append({
                "edgeId": edge_id, "sourceNodeId": source, "targetNodeId": target,
                "direction": raw_direction,
                "weight": abs(weight), "lagDays": int(_numeric(_mapped_value(row, mappings, "NETWORK_EDGE_LAG"), _numeric(parameters.get("lagDays"), 0))),
                "impactCapPct": abs(_numeric(parameters.get("impactCapPct"), 0)),
                "confidence": confidence,
                "candidateWeight": candidate_weight,
                "candidateSimulation": bool(candidate_eligible and candidate_weight > 0),
                "mechanism": str(_mapped_value(row, mappings, "NETWORK_EDGE_MECHANISM") or "").strip(),
                "evidenceSource": evidence or "MISSING", "status": edge_status,
                "sourceStatus": source_status or None,
                "parameterStatus": str(_mapped_value(row, mappings, "NETWORK_EDGE_PARAMETER_STATUS") or "").strip().upper() or None,
                "relationType": relation_type,
                "formulaId": formula_id, "formulaType": formula_type,
                "sourceFormulaType": (formula or {}).get("sourceFormulaType") or declared_formula_type,
                "formulaResolution": (formula or {}).get("formulaResolution") or declared_resolution,
                "formulaSupported": formula_supported, "formulaParameters": parameters,
                "formulaVersion": (formula or {}).get("version") or "implicit-1.0",
                "invalidation": (formula or {}).get("invalidation"),
            })

        causal_edges = [
            item for item in edges
            if item["status"] == "CONFIRMED"
            and item.get("relationType") not in structural_types
            and item.get("formulaSupported", True)
            and item.get("formulaType") in SUPPORTED_FORMULAS
        ]
        candidate_edges = [
            item for item in edges
            if item["status"] == "CANDIDATE"
            and item.get("relationType") not in {"DATA_LINEAGE", "ENTITY_METRIC"}
            and item.get("formulaSupported", True)
            and item.get("formulaType") in SUPPORTED_FORMULAS
            and float(item.get("candidateWeight") or 0) > 0
        ]
        candidate_node_ids = {value for edge in candidate_edges for value in (edge["sourceNodeId"], edge["targetNodeId"])}
        causal_node_ids = {value for edge in causal_edges for value in (edge["sourceNodeId"], edge["targetNodeId"])}
        causal_nodes = [item for item in nodes if item["nodeId"] in causal_node_ids]
        empty_layers = [layer["layerNo"] for layer in layer_records if not any(node["layerNo"] == layer["layerNo"] for node in nodes)]
        if empty_layers:
            warnings.append({"code": "EMPTY_LAYERS", "layerNumbers": empty_layers})
        if not causal_edges:
            warnings.append({"code": "NO_CONFIRMED_CAUSAL_PATH"})

        blocking_codes = {
            "NO_VALID_LAYERS", "NO_VALID_NODES", "DUPLICATE_NODE_ID", "NODE_ID_MISSING",
            "NODE_LAYER_INVALID", "EDGE_NODE_NOT_FOUND", "FORMULA_REFERENCE_NOT_FOUND",
            "FORMULA_TYPE_UNSUPPORTED", "FORMULA_PARAMETERS_INVALID", "EDGE_PARAMETERS_INVALID",
        }
        blocking = [item for item in issues if item.get("code") in blocking_codes]
        validation_status = "INVALID" if blocking else ("VALIDATED_WITH_WARNINGS" if warnings else "VALIDATED")
        definition = {
            "networkId": network_id,
            "networkName": network_name or f"导入网络 {network_id}",
            "schemaVersion": network_version or "multi-table-network-2.0",
            "nodes": nodes, "edges": edges, "formulas": list(formulas.values()),
            "layerLabels": layer_records, "dataCutoff": cutoff,
            "validationStatus": validation_status, "validationIssues": issues, "warnings": warnings,
            "formalReady": not blocking and bool(causal_edges),
            "outputLevel": "SCENARIO_PATH_ONLY" if causal_edges and not blocking else ("ABSTAIN" if blocking else ("CANDIDATE_SCENARIO" if candidate_edges else "EXPOSURE_ONLY")),
            "candidateScenarioReady": bool(candidate_edges) and not blocking,
            "candidateEdgeCount": len(candidate_edges),
            "nodeCount": len(nodes), "edgeCount": len(edges),
            "confirmedEdgeCount": len(causal_edges), "candidateEdgeCount": len(edges) - len(causal_edges),
            "evidenceIds": sorted(evidence_ids), "evidenceRecords": evidence_records,
            "fullGraph": {"nodes": nodes, "edges": edges},
            "causalGraph": {
                "nodes": causal_nodes, "edges": causal_edges,
                "excludedNodeCount": max(0, len(nodes) - len(causal_nodes)),
                "excludedEdgeCount": max(0, len(edges) - len(causal_edges)),
            },
            "candidateGraph": {
                "nodes": [item for item in nodes if item["nodeId"] in candidate_node_ids],
                "edges": candidate_edges,
                "excludedNodeCount": max(0, len(nodes) - len(candidate_node_ids)),
                "excludedEdgeCount": max(0, len(edges) - len(candidate_edges)),
            },
        }
        definitions.append(definition)
    definitions.sort(key=lambda item: (item["validationStatus"] != "VALIDATED", item["validationStatus"] == "INVALID", -(item["nodeCount"] + item["edgeCount"])))
    return definitions

def sync_database(config: dict[str, Any], mappings: list[dict[str, Any]], source_id: str, cutoff: str, entity_codes: list[str] | None = None, row_limit: int = 500, page: int = 0, cancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
    columnar_codes = {"NETWORK_CHAIN_LAYER_NO", "NETWORK_CHAIN_LAYER_NAME", "NETWORK_EDITABLE_METRIC_NAME", "NETWORK_EDITABLE_BASELINE_VALUE", "NETWORK_DRIVER_SENSITIVITY", "NETWORK_LAG_DAYS", "NETWORK_IMPACT_CAP_PCT"}
    if any(item.get("metricCode") in columnar_codes for item in mappings):
        mappings = [item for item in mappings if item.get("metricCode") not in {"NETWORK_NODES_JSON", "NETWORK_EDGES_JSON", "NETWORK_LAYERS_JSON", "NETWORK_METADATA_JSON"}]
    database = str(config.get("database") or config.get("dbname") or "").strip()
    grouped = _mapping_by_table(mappings, str(config.get("schema") or database or "public"), database or None)
    if not grouped:
        raise ValueError("CONFIRMED_MAPPING_REQUIRED")
    database_type = str(config.get("type") or "").lower()
    if database_type not in {"postgresql", "mysql"}:
        raise ValueError("DATABASE_TYPE_NOT_ALLOWED")

    row_limit = max(1, min(int(row_limit), MAX_SYNC_ROWS))
    entity_codes = [str(item) for item in (entity_codes or []) if item]
    page = max(0, int(page))
    snapshot_id = stable_id("SNAP", {"source": source_id, "cutoff": cutoff, "mappings": sorted(item["mappingId"] for item in mappings if item.get("status") == "CONFIRMED"), "page": page})
    all_values: list[dict[str, Any]] = []
    all_evidence: list[dict[str, Any]] = []
    rejection_reasons: dict[str, int] = {}
    precompiled_networks: list[dict[str, Any]] = []
    multi_table_rows: list[tuple[str, list[dict[str, Any]], list[dict[str, Any]], str]] = []
    columnar_networks: list[dict[str, Any]] = []
    table_roles: list[dict[str, Any]] = []
    rows_read = 0
    accepted_rows_count = 0
    successful_tables = 0
    # rowLimit is a per-table safety limit. Dividing it by the number of tables
    # truncates structural packages (nodes/edges/formulas) as more tables are selected.
    per_table_limit = max(1, min(MAX_PAGE_SIZE, row_limit))

    for (schema, table), table_mappings in grouped.items():
        if cancelled and cancelled():
            raise RuntimeError("SYNC_CANCELLED")
        qualified = f"{schema}.{table}"
        codes = {str(item.get("metricCode") or "") for item in table_mappings}
        controls = _controls(table_mappings)
        legacy_precompiled = bool(
            (controls.get("NETWORK_NODES_JSON") and controls.get("NETWORK_EDGES_JSON"))
            or controls.get("NETWORK_METADATA_JSON")
        )
        legacy_columnar = bool(codes.intersection(columnar_codes))
        role = _role_for_mappings(table_mappings)
        if role == "UNKNOWN" and (legacy_precompiled or legacy_columnar):
            status, missing = "READY", []
            display_role = "PRECOMPILED"
        else:
            status, missing = role_status(role, codes)
            display_role = role
        diagnostic = {
            "table": qualified, "role": display_role, "rowsRead": 0,
            "status": status, "missing": missing, "detail": None,
        }
        if status in {"NEEDS_MAPPING", "INCOMPLETE"}:
            table_roles.append(diagnostic)
            continue

        try:
            if database_type == "postgresql":
                rows = _postgres_rows(config, schema, table, table_mappings, cutoff, entity_codes, per_table_limit, page * per_table_limit)
            else:
                rows = _mysql_rows(config, schema, table, table_mappings, cutoff, entity_codes, per_table_limit, page * per_table_limit)
        except Exception as error:
            diagnostic.update({"status": "ERROR", "detail": f"{type(error).__name__}: {error}"[:500]})
            table_roles.append(diagnostic)
            continue

        successful_tables += 1
        diagnostic.update({"status": "READY", "rowsRead": len(rows)})
        table_roles.append(diagnostic)
        rows_read += len(rows)

        if role in STRUCTURAL_ROLES | {"METRIC_VALUES", "CALCULATED_LINEAGE", "FINANCIALS", "VALUATION", "METRICS"}:
            multi_table_rows.append((role, rows, table_mappings, qualified))
        precompiled = None if role in STRUCTURAL_ROLES else _extract_precompiled_network(rows, table_mappings, source_id, cutoff, qualified)
        if precompiled:
            precompiled_networks.append(precompiled)
        columnar = _extract_columnar_precompiled_controls(rows, table_mappings, qualified)
        if columnar:
            columnar_networks.append(columnar)

        values, evidence, rejected = (
            _row_values(rows, table_mappings, source_id, cutoff, snapshot_id, qualified)
            if role in {"FINANCIALS", "METRICS"}
            else ([], [], {})
        )
        all_values.extend(values)
        all_evidence.extend(evidence)
        if role in STRUCTURAL_ROLES | {"METRIC_VALUES", "CALCULATED_LINEAGE", "VALUATION"} or precompiled or columnar:
            accepted_rows_count += len(rows)
        else:
            accepted_rows_count += len({item["sourceRowKey"] for item in values})
        for key, count in rejected.items():
            rejection_reasons[key] = rejection_reasons.get(key, 0) + count

    compiled_networks = _extract_multi_table_network(multi_table_rows, source_id, cutoff)
    precompiled_networks.extend(compiled_networks)
    if len(columnar_networks) > 1:
        table_roles.append({
            "table": "(columnar package)", "role": "PRECOMPILED", "rowsRead": 0,
            "status": "ERROR", "missing": [], "detail": "同一次同步只允许一个列式预编译网络表",
        })
        columnar_networks = columnar_networks[:1]

    def network_score(item: dict[str, Any]) -> tuple[int, int, int]:
        status_score = {"VALIDATED": 3, "VALIDATED_WITH_WARNINGS": 2, "INVALID": 0}.get(str(item.get("validationStatus")), 1)
        return status_score, int(item.get("nodeCount") or 0), int(item.get("edgeCount") or 0)

    precompiled_networks.sort(key=network_score, reverse=True)
    primary_network = precompiled_networks[0] if precompiled_networks else None
    available_networks = [{
        "networkId": item.get("networkId"),
        "networkName": item.get("networkName"),
        "validationStatus": item.get("validationStatus"),
        "formalReady": bool(item.get("formalReady")),
        "outputLevel": item.get("outputLevel"),
        "nodeCount": int(item.get("nodeCount") or len(item.get("nodes") or [])),
        "edgeCount": int(item.get("edgeCount") or len(item.get("edges") or [])),
        "validationIssues": item.get("validationIssues") or [],
        "warnings": item.get("warnings") or [],
    } for item in precompiled_networks]
    sync_status = "READY" if successful_tables == len(grouped) else ("PARTIAL" if successful_tables else "FAILED")
    return {
        "sourceSnapshotId": snapshot_id, "rowsRead": rows_read, "tableRoles": table_roles,
        "syncStatus": sync_status, "successfulTables": successful_tables, "selectedTables": len(grouped),
        "acceptedRows": accepted_rows_count,
        "rejectedRows": max(0, rows_read - accepted_rows_count), "rejectionReasons": rejection_reasons,
        "metricValuesCreated": len(all_values), "metricValues": all_values, "evidence": all_evidence,
        "evidenceIds": [item["evidenceId"] for item in all_evidence], "cutoffStatus": "PASS",
        "dataCutoff": cutoff, "queryMode": "ROLE_AWARE_CONFIRMED_FIELDS_ONLY", "readOnly": True, "page": page,
        "nextPage": page + 1 if successful_tables and rows_read == per_table_limit * successful_tables else None,
        "precompiledNetwork": primary_network,
        "precompiledNetworks": precompiled_networks,
        "availableNetworks": available_networks,
        "precompiledColumnar": columnar_networks[0] if columnar_networks else None,
        "precompiledStatus": (
            str(primary_network.get("validationStatus")) if primary_network
            else ("VALIDATED" if columnar_networks else "NOT_DETECTED")
        ),
    }

def sync_records(records: list[dict[str, Any]], mappings: list[dict[str, Any]], source_id: str, cutoff: str, source_table: str = "uploaded_file", row_limit: int = 500) -> dict[str, Any]:
    confirmed = []
    for item in mappings:
        if item.get("status") != "CONFIRMED" or not _metric_for_mapping(item):
            continue
        confirmed.append({**item, "table": source_table, "column": str(item.get("sourceField") or item.get("sourceColumn"))})
    if not confirmed:
        raise ValueError("CONFIRMED_MAPPING_REQUIRED")
    snapshot_id = stable_id("SNAP", {"source": source_id, "cutoff": cutoff, "mappings": sorted(item["mappingId"] for item in confirmed), "page": 0})
    rows = records[:max(1, min(int(row_limit), MAX_SYNC_ROWS))]
    precompiled = _extract_precompiled_network(rows, confirmed, source_id, cutoff, source_table)
    if precompiled:
        values, evidence, rejected = [], [], {}
    else:
        if not any(item["metricCode"] == "ENTITY_CODE" for item in confirmed) or not any(item["metricCode"] == "REPORT_PERIOD" for item in confirmed):
            raise ValueError("CONFIRMED_CONTROL_FIELDS_REQUIRED:ENTITY_CODE,REPORT_PERIOD")
        values, evidence, rejected = _row_values(rows, confirmed, source_id, cutoff, snapshot_id, source_table)
    return {
        "sourceSnapshotId": snapshot_id, "rowsRead": len(rows),
        "acceptedRows": len({item["sourceRowKey"] for item in values}), "rejectedRows": max(0, len(rows) - len({item["sourceRowKey"] for item in values})),
        "rejectionReasons": rejected, "metricValuesCreated": len(values), "metricValues": values, "evidence": evidence,
        "evidenceIds": [item["evidenceId"] for item in evidence], "cutoffStatus": "PASS", "dataCutoff": cutoff,
        "queryMode": "CONFIRMED_FIELDS_ONLY", "readOnly": True,
        "precompiledNetwork": precompiled, "precompiledStatus": "VALIDATED" if precompiled else "NOT_DETECTED",
    }


COMPANY_NAMES = {"601088.SH": "中国神华", "601225.SH": "陕西煤业", "600188.SH": "兖矿能源", "600019.SH": "宝钢股份", "000708.SZ": "中信特钢"}
COMPANY_MODELS = {"601088.SH": "DIVERSIFIED_MINER", "601225.SH": "PURE_MINER", "600188.SH": "MIXED_MINER", "600019.SH": "INTEGRATED_STEEL", "000708.SZ": "SPECIAL_STEEL"}
COMPANY_NODE_IDS = {
    "601088.SH": "shenhua",
    "601225.SH": "shaanxi",
    "600188.SH": "yankuang",
    "600019.SH": "baosteel",
    "000708.SZ": "citicsteel",
}


def latest_metric_values(values: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for item in values:
        key = (item["entityCode"], item["metricCode"])
        marker = (str(item.get("reportPeriod") or ""), str(item.get("announcementDate") or ""), str(item.get("opdate") or ""))
        previous = latest.get(key)
        previous_marker = (str(previous.get("reportPeriod") or ""), str(previous.get("announcementDate") or ""), str(previous.get("opdate") or "")) if previous else ("", "", "")
        if marker >= previous_marker:
            latest[key] = item
    return latest


def build_precompiled_network_plan(source_id: str, definition: dict[str, Any], network_name: str | None = None) -> dict[str, Any]:
    nodes = definition.get("nodes") or []
    edges = definition.get("edges") or []
    structural_types = {"DATA_LINEAGE", "ENTITY_METRIC", "ACCOUNTING_STRUCTURE"}
    scenario_edges = [
        item for item in edges
        if item.get("status") == "CONFIRMED"
        and item.get("relationType") not in structural_types
        and item.get("formulaType", "LINEAR_WEIGHT") in SUPPORTED_FORMULAS
    ]
    causal_node_ids = {value for edge in scenario_edges for value in (edge.get("sourceNodeId"), edge.get("targetNodeId"))}
    causal_graph = definition.get("causalGraph") or {
        "nodes": [item for item in nodes if item.get("nodeId") in causal_node_ids],
        "edges": scenario_edges,
        "excludedNodeCount": max(0, len(nodes) - len(causal_node_ids)),
        "excludedEdgeCount": max(0, len(edges) - len(scenario_edges)),
    }
    candidate_graph = definition.get("candidateGraph") or {"nodes": [], "edges": [], "excludedNodeCount": len(nodes), "excludedEdgeCount": len(edges)}
    company_gaps = [{
        "entityCode": item.get("entityCode") or item.get("nodeId"), "status": "COMPANY_ADAPTER_REQUIRED",
        "missing": ["公司经营模型", "财务桥接公式", "估值方法"],
    } for item in nodes if (item.get("layer") == "company" or int(item.get("layerNo") or 0) == 6) and not item.get("companyModel")]
    validation_issues = definition.get("validationIssues") or []
    activation_blocked = str(definition.get("validationStatus") or "").upper() == "INVALID"
    plan_id = stable_id("PLAN", {"source": source_id, "network": definition.get("networkId"), "version": definition.get("schemaVersion"), "nodes": [item.get("nodeId") for item in nodes], "edges": [item.get("edgeId") for item in edges], "formulas": definition.get("formulas") or []})
    return {
        "networkPlanId": plan_id, "sourceNetworkId": definition.get("networkId"),
        "sourceId": source_id, "domainId": "precompiled", "mode": "CREATE_NEW_NETWORK",
        "networkKind": "MULTI_TABLE_NETWORK" if str(definition.get("schemaVersion") or "").startswith("multi-table") else "PRECOMPILED_NETWORK",
        "networkName": network_name or definition.get("networkName") or "预编译网络",
        "status": "PENDING_REVIEW", "createdAt": now(),
        "formalReady": bool(definition.get("formalReady")) and not activation_blocked,
        "activationBlocked": activation_blocked,
        "causalStatus": "CONDITIONAL" if scenario_edges and not activation_blocked else "ABSTAIN",
        "outputLevel": "CANDIDATE_SCENARIO" if definition.get("candidateScenarioReady") and not scenario_edges and not activation_blocked else (definition.get("outputLevel") or ("SCENARIO_PATH_ONLY" if scenario_edges else "EXPOSURE_ONLY")),
        "layerLabels": definition.get("layerLabels") or SOURCE_DEFINED_LAYER_LABELS,
        "formulas": definition.get("formulas") or [],
        "validationStatus": definition.get("validationStatus") or "VALIDATED",
        "validationIssues": validation_issues, "warnings": definition.get("warnings") or [],
        "precompiled": {key: definition.get(key) for key in ("networkId", "schemaVersion", "sourceTable", "dataCutoff", "validationStatus", "nodeCount", "edgeCount", "confirmedEdgeCount", "candidateEdgeCount")},
        "graph": definition.get("fullGraph") or {"nodes": nodes, "edges": edges},
        "fullGraph": definition.get("fullGraph") or {"nodes": nodes, "edges": edges},
        "causalGraph": causal_graph,
        "diff": {
            "addedNodes": nodes, "updatedNodes": [], "removedNodes": [], "sharedNodes": [], "unavailableNodes": [],
            "addedEdges": edges, "removedEdges": [], "baselineChanges": [], "formulaChanges": [],
            "evidenceGaps": [item.get("edgeId") for item in edges if item.get("status") == "CANDIDATE"],
            "companyAdapterGaps": company_gaps,
        },
        "simulationReady": bool(scenario_edges) and not activation_blocked,
            "candidateScenarioReady": bool(definition.get("candidateScenarioReady")) and not activation_blocked,
        "candidateGraph": candidate_graph,
    }

def build_columnar_precompiled_network_plan(source_id: str, values: list[dict[str, Any]], definition: dict[str, Any], network_name: str | None = None) -> dict[str, Any]:
    plan = build_generated_network_plan(source_id, values, network_name)
    controls = definition.get("controls") or []
    graph = plan["graph"]
    node_ids = {item.get("nodeId") for item in graph["nodes"]}
    entities = {item.get("entityCode"): item for item in graph["nodes"] if item.get("layer") == "company"}
    driver_nodes: dict[str, dict[str, Any]] = {}
    parameter_edges = []
    for control in controls:
        metric_name = str(control.get("editableMetricName") or "").strip()
        if not metric_name:
            continue
        metric_code = str(control.get("editableMetricCode") or "").strip() or "DRIVER_" + hashlib.sha256(metric_name.encode("utf-8")).hexdigest()[:12].upper()
        driver_id = "driver-" + hashlib.sha256(metric_code.encode("utf-8")).hexdigest()[:12]
        if driver_id not in driver_nodes:
            kind = str(control.get("editableMetricType") or "index").lower()
            layer = "macro" if kind in {"macro", "policy", "rate"} else "demand"
            driver_nodes[driver_id] = {
                "nodeId": driver_id, "layer": layer, "label": metric_name,
                "sub": f"可调{METRIC_TYPE_LABELS.get(kind, '指标')} · {control.get('editableMetricUnit') or '%'}",
                "source": "PRECOMPILED_COLUMN_NETWORK", "status": "CONFIRMED_DATA",
                "metricCodes": [metric_code], "metricType": kind,
                "unit": control.get("editableMetricUnit") or "%",
                "baseline": {"BASE": control.get("editableBaselineValue")},
                "evidenceIds": [definition.get("sourceTable") or "PRECOMPILED_COLUMN_NETWORK"],
                "description": "由预编译网络表的可调指标定义生成；调整值表示相对基准的条件情景变化。",
                "valueStatus": "ANALYST_ASSUMPTION", "editableDefinition": True,
            }
        entity = entities.get(control.get("entityCode"))
        if not entity:
            continue
        sensitivity = float(control.get("driverSensitivity") or 0)
        edge = {
            "edgeId": stable_id("EDGE", {"source": source_id, "driver": driver_id, "entity": control.get("entityCode")}),
            "sourceNodeId": driver_id, "targetNodeId": entity["nodeId"],
            "direction": control.get("direction") or ("negative" if sensitivity < 0 else "positive"),
            "weight": abs(sensitivity), "lagDays": int(control.get("lagDays") or 0),
            "impactCapPct": float(control.get("impactCapPct") or 0), "confidence": 0.85,
            "mechanism": control.get("mechanism"),
            "evidenceSource": [definition.get("sourceTable") or "PRECOMPILED_COLUMN_NETWORK", "USER_CURATED_PARAMETER"],
            "status": "CONFIRMED", "relationType": "PRECOMPILED_PARAMETER_EDGE",
            "parameterStatus": "ANALYST_ASSUMPTION",
        }
        parameter_edges.append(edge)
    for node in driver_nodes.values():
        if node["nodeId"] not in node_ids:
            graph["nodes"].append(node)
            node_ids.add(node["nodeId"])
    graph["edges"].extend(parameter_edges)
    # Compile a strict causal subgraph for the main canvas. Evidence-only and accounting
    # lineage nodes remain in graph for audit inspection but are excluded from propagation.
    causal_edges = [edge for edge in parameter_edges if edge.get("status") == "CONFIRMED" and float(edge.get("weight") or 0) > 0]
    causal_ids = {"import-snapshot"}
    causal_ids.update(edge.get("sourceNodeId") for edge in causal_edges)
    causal_ids.update(edge.get("targetNodeId") for edge in causal_edges)
    causal_nodes = [node for node in graph["nodes"] if node.get("nodeId") in causal_ids]
    causal_graph = {"nodes": causal_nodes, "edges": causal_edges, "excludedNodeCount": max(0, len(graph["nodes"]) - len(causal_nodes)), "excludedEdgeCount": max(0, len(graph["edges"]) - len(causal_edges))}
    plan.update({
        "networkPlanId": stable_id("PLAN", {"source": source_id, "values": sorted(item["metricValueId"] for item in values), "columnar": controls}),
        "networkKind": "PRECOMPILED_COLUMN_NETWORK", "domainId": "precompiled-columnar",
        "outputLevel": "SCENARIO_PATH_ONLY" if parameter_edges else "EXPOSURE_ONLY",
        "simulationReady": bool(parameter_edges),
        "causalGraph": causal_graph,
        "precompiled": {
            "adapterMode": "PRECOMPILED_NETWORK_COLUMNS", "validationStatus": definition.get("validationStatus"),
            "sourceTable": definition.get("sourceTable"), "controlRows": len(controls),
            "driverNodes": len(driver_nodes), "parameterEdges": len(parameter_edges),
        },
    })
    plan["diff"]["addedEdges"] = graph["edges"]
    plan["diff"]["evidenceGaps"] = ["COMPANY_ADAPTER_NOT_ACTIVATED", "PARAMETERS_CLASSIFIED_AS_ANALYST_ASSUMPTION"]
    return plan


def build_network_plan(source_id: str, values: list[dict[str, Any]], domain_id: str = "coal-steel", mode: str = "UPDATE_EXISTING", network_name: str | None = None, precompiled_network: dict[str, Any] | None = None, precompiled_columnar: dict[str, Any] | None = None) -> dict[str, Any]:
    if mode == "CREATE_NEW_NETWORK":
        if precompiled_network:
            return build_precompiled_network_plan(source_id, precompiled_network, network_name)
        if precompiled_columnar:
            return build_columnar_precompiled_network_plan(source_id, values, precompiled_columnar, network_name)
        return build_generated_network_plan(source_id, values, network_name)
    latest = latest_metric_values(values)
    entities = sorted({entity for entity, _ in latest})
    updated_nodes = []
    added_nodes = []
    adapter_gaps = []
    for entity in entities:
        metrics = {code: item for (code_entity, code), item in latest.items() if code_entity == entity}
        node = {
            "nodeId": COMPANY_NODE_IDS.get(entity, f"company-{entity.lower().replace('.', '-')}"), "layer": "company", "label": COMPANY_NAMES.get(entity, entity),
            "entityCode": entity, "source": "STANDARD_METRIC_VALUES", "metricCodes": sorted(metrics),
            "baseline": {code: item["value"] for code, item in metrics.items()},
            "evidenceIds": sorted({item["evidenceId"] for item in metrics.values()}),
            "status": "CANDIDATE", "companyModel": COMPANY_MODELS.get(entity),
        }
        if entity in COMPANY_NAMES:
            updated_nodes.append(node)
        else:
            node["status"] = "COMPANY_ADAPTER_REQUIRED"
            added_nodes.append(node)
            adapter_gaps.append({"entityCode": entity, "status": "COMPANY_ADAPTER_REQUIRED", "missing": ["产业位置证据", "经营暴露权重", "公司模型家族"]})
    plan = {
        "networkPlanId": stable_id("PLAN", {"source": source_id, "entities": entities, "values": sorted(item["metricValueId"] for item in values)}),
        "sourceId": source_id, "domainId": domain_id, "mode": "UPDATE_EXISTING", "networkKind": "DOMAIN_OVERLAY",
        "networkName": network_name or "焦煤—钢铁数据更新", "status": "PENDING_REVIEW", "createdAt": now(),
        "diff": {
            "addedNodes": added_nodes, "updatedNodes": updated_nodes, "removedNodes": [],
            "sharedNodes": ["rates"], "unavailableNodes": [], "addedEdges": [], "removedEdges": [],
            "evidenceGaps": [] if values else ["STANDARD_METRIC_VALUES_MISSING"], "companyAdapterGaps": adapter_gaps,
        },
        "formalReady": False, "causalStatus": "ABSTAIN",
    }
    return plan


GENERATED_LAYER_LABELS = [
    {"id": "macro", "label": "数据范围 / 时间", "subtitle": "SOURCE & CUTOFF"},
    {"id": "demand", "label": "收入与业务规模", "subtitle": "REVENUE & SCALE"},
    {"id": "route", "label": "成本与经营投入", "subtitle": "COST & OPERATIONS"},
    {"id": "constraint", "label": "资产与资本约束", "subtitle": "BALANCE SHEET"},
    {"id": "chain", "label": "利润与现金流", "subtitle": "PROFIT & CASH FLOW"},
    {"id": "company", "label": "公司 / 数据实体", "subtitle": "ENTITIES"},
]
SOURCE_DEFINED_LAYER_LABELS = [
    {"id": "macro", "label": "数据范围 / 时间", "subtitle": "SOURCE & CUTOFF"},
    {"id": "demand", "label": "市场与成长", "subtitle": "MARKET & GROWTH"},
    {"id": "route", "label": "运营与效率", "subtitle": "OPERATIONS & EFFICIENCY"},
    {"id": "constraint", "label": "资本与风险", "subtitle": "CAPITAL & RISK"},
    {"id": "chain", "label": "结果与质量", "subtitle": "OUTCOME & QUALITY"},
    {"id": "company", "label": "公司 / 数据实体", "subtitle": "ENTITIES"},
]

GENERATED_METRIC_LAYERS = {
    "REVENUE": "demand",
    "STEEL_DEMAND": "demand",
    "STEEL_PRICE": "demand",
    "OPERATING_COST": "route",
    "CAPEX": "route",
    "BLAST_FURNACE_UTILIZATION": "route",
    "CASH": "constraint",
    "INVENTORY": "constraint",
    "ACCOUNTS_RECEIVABLE": "constraint",
    "NOTES_RECEIVABLE": "constraint",
    "PREPAYMENTS": "constraint",
    "TRADING_FINANCIAL_ASSETS": "constraint",
    "TOTAL_ASSETS": "constraint",
    "TOTAL_LIABILITIES": "constraint",
    "SHORT_TERM_DEBT": "constraint",
    "LONG_TERM_DEBT": "constraint",
    "BONDS_PAYABLE": "constraint",
    "LEASE_LIABILITY": "constraint",
    "CURRENT_PORTION_DEBT": "constraint",
    "MINORITY_INTEREST": "constraint",
    "TOTAL_SHARES": "constraint",
    "STEEL_INVENTORY": "constraint",
    "JM_PRICE": "constraint",
    "OPERATING_PROFIT": "chain",
    "NET_PROFIT": "chain",
    "EBIT": "chain",
    "EBITDA": "chain",
    "EPS_BASIC": "chain",
    "EPS_DILUTED": "chain",
    "OPERATING_CASH_FLOW": "chain",
    "FREE_CASH_FLOW": "chain",
    "ENDING_CASH": "chain",
    "EQUITY": "chain",
    "GROSS_PROFIT": "chain",
    "TOTAL_DEBT": "constraint",
    "NET_DEBT": "constraint",
    "REVENUE_GROWTH_PCT": "demand",
    "NET_PROFIT_GROWTH_PCT": "chain",
    "GROSS_MARGIN_PCT": "chain",
    "OPERATING_MARGIN_PCT": "chain",
    "NET_MARGIN_PCT": "chain",
    "FCF_MARGIN_PCT": "chain",
    "ASSET_LIABILITY_RATIO_PCT": "constraint",
}

GENERATED_METRIC_PRIORITY = [
    "REVENUE", "STEEL_DEMAND", "STEEL_PRICE", "OPERATING_COST", "CAPEX", "BLAST_FURNACE_UTILIZATION",
    "TOTAL_ASSETS", "TOTAL_LIABILITIES", "CASH", "INVENTORY", "ACCOUNTS_RECEIVABLE",
    "SHORT_TERM_DEBT", "LONG_TERM_DEBT", "BONDS_PAYABLE", "LEASE_LIABILITY", "TOTAL_DEBT", "NET_DEBT", "TOTAL_SHARES",
    "GROSS_PROFIT", "OPERATING_PROFIT", "NET_PROFIT", "EBIT", "EBITDA", "OPERATING_CASH_FLOW",
    "FREE_CASH_FLOW", "ENDING_CASH", "EQUITY", "EPS_BASIC", "REVENUE_GROWTH_PCT",
    "NET_PROFIT_GROWTH_PCT", "GROSS_MARGIN_PCT", "OPERATING_MARGIN_PCT", "NET_MARGIN_PCT",
    "FCF_MARGIN_PCT", "ASSET_LIABILITY_RATIO_PCT",
]

GENERATED_ACCOUNTING_RELATIONS = [
    ("REVENUE", "OPERATING_PROFIT", "positive", "营业收入是营业利润结构的一项输入；完整计算仍需税金及期间费用。"),
    ("OPERATING_COST", "OPERATING_PROFIT", "negative", "营业成本增加在其他条件不变时压低营业利润；这不是完整利润恒等式。"),
    ("OPERATING_PROFIT", "NET_PROFIT", "positive", "营业利润经非经营项目、税项及少数股东损益桥接至归母净利润。"),
    ("EBIT", "NET_PROFIT", "positive", "EBIT 经利息、税项及归属口径桥接至归母净利润。"),
    ("OPERATING_CASH_FLOW", "FREE_CASH_FLOW", "positive", "自由现金流以经营现金流为主要流入项。"),
    ("CAPEX", "FREE_CASH_FLOW", "negative", "资本开支是自由现金流计算中的扣减项。"),
    ("CASH", "ENDING_CASH", "positive", "资产负债表货币资金与现金流量表期末现金存在口径关联，需核对受限资金。"),
    ("TOTAL_LIABILITIES", "EQUITY", "negative", "资产不变条件下，负债与权益存在会计结构约束；不表示已识别因果。"),
]


def _generated_node_id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "node"
    # Chinese names and exchange/name composite keys collapse to one ASCII slug.
    if prefix == "entity" and not str(value).isascii():
        slug = slug + "-" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:8]
    return prefix + "-" + slug


def _generated_metric_layer(code: str, metric: dict[str, Any]) -> str:
    explicit = str(metric.get("networkLayer") or "")
    if explicit in {"demand", "route", "constraint", "chain"}:
        return explicit
    if code in GENERATED_METRIC_LAYERS:
        return GENERATED_METRIC_LAYERS[code]
    text = str(metric.get("metricName") or "").lower()
    semantic = (
        ("demand", ("规模", "成长", "收入", "增长", "市场", "需求")),
        ("route", ("运营", "营运", "周转", "效率", "成本", "投入")),
        ("constraint", ("偿债", "风险", "资本", "资产", "负债", "杠杆")),
        ("chain", ("盈利", "质量", "利润", "现金", "回报", "收益")),
    )
    for layer, tokens in semantic:
        if any(token in text for token in tokens):
            return layer
    return ("demand", "route", "constraint", "chain")[int(hashlib.sha256(code.encode()).hexdigest()[:2], 16) % 4]


METRIC_TYPE_LABELS = {"price": "价格", "flow": "期间流量", "stock": "时点存量", "ratio": "比例", "score": "评分", "count": "数量", "index": "指数", "numeric": "数值"}
UNIT_LABELS = {"SOURCE_UNIT_UNKNOWN": "单位待确认", "CURRENCY": "金额", "PERCENT": "百分比", "INDEX": "指数", "SHARES": "股数", None: "单位待确认"}


def _metric_subtitle(metric: dict[str, Any]) -> str:
    kind = METRIC_TYPE_LABELS.get(str(metric.get("metricType") or "").lower(), "指标")
    unit = UNIT_LABELS.get(metric.get("unit"), str(metric.get("unit") or "单位待确认"))
    return f"{kind} · {unit}"

def build_generated_network_plan(source_id: str, values: list[dict[str, Any]], network_name: str | None = None) -> dict[str, Any]:
    latest = latest_metric_values(values)
    all_entities = sorted({entity for entity, _ in latest})
    entities = all_entities[:20]
    # Do not promote opaque technical columns to visible network nodes. Standard metrics and explicitly localized/AI-confirmed custom metrics are displayable; unresolved English fields remain in the audit mapping only.
    present_codes = set()
    for (entity, code), item in latest.items():
        if code in DIMENSION_CODES:
            continue
        metric_name = str(item.get("metricName") or "")
        semantic_source = str(item.get("semanticSource") or "")
        if code in METRIC_BY_CODE or re.search(r"[\u4e00-\u9fff]", metric_name) or semantic_source in {"AI_CONFIRMED_BY_USER", "COLUMN_COMMENT", "FINANCIAL_FIELD_DICTIONARY"}:
            present_codes.add(code)
    source_defined = any(code.startswith("CUSTOM_") for code in present_codes)
    layer_labels = SOURCE_DEFINED_LAYER_LABELS if source_defined else GENERATED_LAYER_LABELS
    network_kind = "SOURCE_DEFINED_NETWORK" if source_defined else "FINANCIAL_DISCLOSURE_NETWORK"
    all_ordered_codes = [code for code in GENERATED_METRIC_PRIORITY if code in present_codes]
    all_ordered_codes.extend(sorted(present_codes - set(all_ordered_codes)))
    layer_counts: dict[str, int] = {}
    ordered_codes = []
    for code in all_ordered_codes:
        sample = next((item for (_, metric_code), item in latest.items() if metric_code == code), {})
        layer = _generated_metric_layer(code, sample)
        # Imported/precompiled tables commonly contain a complete financial
        # bridge (income statement, balance sheet, cash flow and ratios). Keep
        # enough room for those confirmed metrics instead of silently dropping
        # valid fields at the old eight-node display cap.
        if layer_counts.get(layer, 0) >= 20:
            continue
        ordered_codes.append(code)
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    cutoff = max((str(item.get("dataCutoff") or "") for item in latest.values()), default="")
    periods = sorted({str(item.get("reportPeriod") or "") for item in latest.values() if item.get("reportPeriod")})
    graph_nodes: list[dict[str, Any]] = [{
        "nodeId": "import-snapshot", "layer": "macro", "label": "导入数据快照", "sub": cutoff or "NO CUTOFF",
        "source": "SOURCE_SNAPSHOT", "status": "CONFIRMED_DATA", "metricCodes": [],
        "baseline": {"entityCount": len(all_entities), "displayedEntityCount": len(entities), "metricCount": len(ordered_codes)},
        "evidenceIds": sorted({item["evidenceId"] for item in latest.values()}),
        "description": f"只读导入；截止 {cutoff or '未识别'}；报告期 {periods[-1] if periods else '未识别'}。",
    }]
    metric_node_ids: dict[str, str] = {}
    for code in ordered_codes:
        sample = next((item for (_, metric_code), item in latest.items() if metric_code == code), {})
        metric = METRIC_BY_CODE.get(code, {"metricName": sample.get("metricName") or code, "metricType": sample.get("metricType") or "unknown", "unit": sample.get("unit"), "networkLayer": sample.get("networkLayer"), "description": sample.get("metricDescription"), "semanticSource": sample.get("semanticSource")})
        by_entity = {entity: item["value"] for (entity, metric_code), item in latest.items() if metric_code == code}
        items = [item for (entity, metric_code), item in latest.items() if metric_code == code]
        node_id = _generated_node_id("metric", code)
        metric_node_ids[code] = node_id
        graph_nodes.append({
            "nodeId": node_id, "layer": _generated_metric_layer(code, metric),
            "label": metric["metricName"], "sub": _metric_subtitle(metric), "source": "STANDARD_METRIC_VALUES",
            "status": "CONFIRMED_DATA", "metricCodes": [code], "metricType": metric.get("metricType"),
            "unit": metric.get("unit"), "baseline": by_entity,
            "evidenceIds": sorted({item["evidenceId"] for item in items}),
            "description": metric.get("description") or "由已确认字段映射生成的来源指标节点；数值按实体保留，不进行跨实体求和。",
            "semanticSource": metric.get("semanticSource"), "semanticConfidence": sample.get("semanticConfidence"), "semanticReason": sample.get("semanticReason"),
        })
    for entity_index, entity in enumerate(entities):
        metrics = {code: item for (item_entity, code), item in latest.items() if item_entity == entity}
        entity_name = COMPANY_NAMES.get(entity) or next((item.get("entityName") for (item_entity, _), item in latest.items() if item_entity == entity and item.get("entityName")), None)
        display_name = entity_name or (f"数据记录 {entity_index + 1:02d}" if entity.startswith("ROW-") else entity)
        entity_sub = entity if not entity.startswith("ROW-") else f"自动行标识 · {entity[-8:]}"
        graph_nodes.append({
            "nodeId": _generated_node_id("entity", entity), "layer": "company",
            "label": display_name, "sub": entity_sub, "entityCode": entity,
            "source": "STANDARD_METRIC_VALUES", "status": "EXPOSURE_ONLY",
            "companyModel": COMPANY_MODELS.get(entity), "metricCodes": sorted(metrics),
            "baseline": {code: item["value"] for code, item in metrics.items()},
            "evidenceIds": sorted({item["evidenceId"] for item in metrics.values()}),
            "description": "本次导入中的数据实体；未加载经审核的关系和实体适配器，不输出情景估值。",
        })
    graph_edges: list[dict[str, Any]] = []
    for layer in ("demand", "route", "constraint", "chain"):
        first = next((node for node in graph_nodes if node["layer"] == layer), None)
        if first:
            graph_edges.append({
                "edgeId": stable_id("EDGE", {"source": source_id, "scope": first["nodeId"]}),
                "sourceNodeId": "import-snapshot", "targetNodeId": first["nodeId"], "direction": "mixed",
                "weight": 0, "lagDays": 0, "confidence": 1.0, "mechanism": "该指标来自同一只读数据快照。",
                "evidenceSource": first["evidenceIds"], "status": "CONFIRMED_LINEAGE", "relationType": "DATA_LINEAGE",
            })
    for source_code, target_code, direction, mechanism in GENERATED_ACCOUNTING_RELATIONS:
        if source_code in metric_node_ids and target_code in metric_node_ids:
            graph_edges.append({
                "edgeId": stable_id("EDGE", {"source": source_id, "from": source_code, "to": target_code}),
                "sourceNodeId": metric_node_ids[source_code], "targetNodeId": metric_node_ids[target_code],
                "direction": direction, "weight": 0, "lagDays": 0, "confidence": 0.85,
                "mechanism": mechanism, "evidenceSource": "ACCOUNTING_STRUCTURE_V1.0",
                "status": "CONFIRMED_STRUCTURE", "relationType": "ACCOUNTING_STRUCTURE",
            })
    # Every displayed metric with an entity value gets a lineage edge. The
    # canvas de-emphasizes unrelated edges until a node is selected, avoiding
    # the previous tradeoff where a cleaner picture silently lost links.
    lineage_codes = ordered_codes
    for entity in entities:
        target_id = _generated_node_id("entity", entity)
        for code in lineage_codes:
            item = latest.get((entity, code))
            if not item or code not in metric_node_ids:
                continue
            graph_edges.append({
                "edgeId": stable_id("EDGE", {"entity": entity, "metric": code}),
                "sourceNodeId": metric_node_ids[code], "targetNodeId": target_id, "direction": "mixed",
                "weight": 0, "lagDays": 0, "confidence": 1.0,
                "mechanism": f"{next((node.get('label') for node in graph_nodes if node.get('nodeId') == metric_node_ids[code]), code)} 是该实体在当前截止时间可见的已确认来源指标。",
                "evidenceSource": [item["evidenceId"]], "status": "CONFIRMED_LINEAGE", "relationType": "ENTITY_METRIC",
            })
    name = (network_name or "").strip() or ("导入数据独立网络" if source_defined else "导入财务披露网络")
    plan_id = stable_id("PLAN", {"source": source_id, "mode": "CREATE_NEW_NETWORK", "name": name, "values": sorted(item["metricValueId"] for item in values)})
    plan = {
        "networkPlanId": plan_id, "sourceId": source_id, "domainId": "generated-source-defined" if source_defined else "generated-financial",
        "mode": "CREATE_NEW_NETWORK", "networkKind": network_kind,
        "networkName": name, "status": "PENDING_REVIEW", "createdAt": now(),
        "outputLevel": "EXPOSURE_ONLY", "formalReady": False, "causalStatus": "ABSTAIN",
        "layerLabels": layer_labels,
        "graph": {"nodes": graph_nodes, "edges": graph_edges},
        "diff": {
            "addedNodes": graph_nodes, "updatedNodes": [], "removedNodes": [{"scope": "ACTIVE_DOMAIN_NETWORK", "status": "REPLACED_IN_VIEW"}],
            "sharedNodes": [], "unavailableNodes": [], "addedEdges": graph_edges, "removedEdges": [],
            "evidenceGaps": ["INDUSTRY_CAUSAL_EDGES_MISSING", "COMPANY_ADAPTER_NOT_ACTIVATED"] + ([f"DISPLAY_METRICS_OMITTED:{len(all_ordered_codes) - len(ordered_codes)}"] if len(all_ordered_codes) > len(ordered_codes) else []) + ([f"DISPLAY_ENTITIES_OMITTED:{len(all_entities) - len(entities)}"] if len(all_entities) > len(entities) else []),
            "companyAdapterGaps": [{"entityCode": entity, "status": "EXPOSURE_ONLY", "missing": ["产业位置证据", "经营暴露权重", "情景模型"]} for entity in entities],
        },
    }
    return plan


BASE_NODES = [
    {"nodeId": "cokingCoalPrice", "layer": "macro", "label": "焦煤价格", "unit": "%", "source": "COAL_STEEL_DOMAIN_V1.0"},
    {"nodeId": "steelRawCost", "layer": "demand", "label": "钢铁原料成本", "unit": "%", "source": "COAL_STEEL_DOMAIN_V1.0"},
    {"nodeId": "steelOrders", "layer": "demand", "label": "钢材订单", "unit": "%", "source": "COAL_STEEL_DOMAIN_V1.0"},
    {"nodeId": "blastFurnacePool", "layer": "chain", "label": "普钢冶炼价值池", "unit": "%", "source": "COAL_STEEL_DOMAIN_V1.0"},
]
BASE_EDGES = [
    {"edgeId": "edge-12", "sourceNodeId": "cokingCoalPrice", "targetNodeId": "steelRawCost", "direction": "positive", "weight": 0.70, "lagDays": 30, "confidence": 0.82, "mechanism": "焦煤价格变化按成本权重进入钢铁原料成本", "evidenceSource": "COAL_STEEL_DOMAIN_V1.0", "status": "CONFIRMED"},
    {"edgeId": "edge-13", "sourceNodeId": "steelRawCost", "targetNodeId": "blastFurnacePool", "direction": "negative", "weight": 0.60, "lagDays": 45, "confidence": 0.78, "mechanism": "原料成本与钢价不变假设下反向影响高炉利润", "evidenceSource": "COAL_STEEL_DOMAIN_V1.0", "status": "CONFIRMED"},
    {"edgeId": "edge-14", "sourceNodeId": "steelOrders", "targetNodeId": "blastFurnacePool", "direction": "positive", "weight": 0.58, "lagDays": 60, "confidence": 0.74, "mechanism": "订单变化影响产能利用率与利润", "evidenceSource": "COAL_STEEL_DOMAIN_V1.0", "status": "CONFIRMED"},
]


def active_graph(plan: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if plan and plan.get("status") == "ACTIVE" and plan.get("mode") == "CREATE_NEW_NETWORK":
        nodes = [{**item, "networkPlanId": plan["networkPlanId"]} for item in plan.get("graph", {}).get("nodes", [])]
        edges = [dict(item) for item in plan.get("graph", {}).get("edges", [])]
        return nodes, edges
    nodes = [dict(item) for item in BASE_NODES]
    edges = [dict(item) for item in BASE_EDGES]
    if not plan or plan.get("status") != "ACTIVE":
        return nodes, edges
    for node in plan["diff"]["updatedNodes"] + plan["diff"]["addedNodes"]:
        active_node = dict(node)
        if active_node.get("status") != "COMPANY_ADAPTER_REQUIRED":
            active_node["status"] = "CONFIRMED"
        active_node["networkPlanId"] = plan["networkPlanId"]
        nodes.append(active_node)
        if node.get("status") != "COMPANY_ADAPTER_REQUIRED":
            edges.append({
                "edgeId": stable_id("EDGE", {"target": node["nodeId"]}), "sourceNodeId": "blastFurnacePool", "targetNodeId": node["nodeId"],
                "direction": "positive", "weight": 0.72, "lagDays": 90, "confidence": 0.68,
                "mechanism": "行业利润变化经公司模型和已同步财务基线进入公司结果", "evidenceSource": node["evidenceIds"], "status": "CONFIRMED",
            })
    valid_nodes = {item["nodeId"] for item in nodes}
    for edge in plan.get("diff", {}).get("addedEdges", []):
        if edge.get("status") == "CONFIRMED" and edge.get("sourceNodeId") in valid_nodes and edge.get("targetNodeId") in valid_nodes:
            edges.append(dict(edge))
    return nodes, edges


MODEL_FACTORS = {"DIVERSIFIED_MINER": 0.18, "PURE_MINER": 0.35, "MIXED_MINER": 0.26, "INTEGRATED_STEEL": -0.22, "SPECIAL_STEEL": -0.11}


def evaluate_formula(formula_type: str, source_change: float, weight: float, direction: str, parameters: dict[str, Any] | None = None) -> tuple[float, str]:
    parameters = parameters or {}
    sign = -1.0 if direction == "negative" else 1.0
    formula = str(formula_type or "LINEAR_WEIGHT").upper()
    coefficient = abs(_numeric(parameters.get("coefficient"), weight))
    if formula in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "IDENTITY", "PERCENT_CHANGE", "LAG"}:
        output = source_change * coefficient
        if formula == "DIVIDE":
            divisor = abs(_numeric(parameters.get("divisor"), 1.0))
            output = output / divisor if divisor else 0.0
    elif formula in {"MIN", "MAX", "CLAMP"}:
        output = source_change * coefficient
        minimum = _numeric(parameters.get("minimum"), _numeric(parameters.get("min"), -300.0))
        maximum = _numeric(parameters.get("maximum"), _numeric(parameters.get("max"), 300.0))
        if formula == "MIN":
            output = max(minimum, output)
        elif formula == "MAX":
            output = min(maximum, output)
        else:
            output = max(minimum, min(maximum, output))
    elif formula == "PRICE_VOLUME":
        price_elasticity = _numeric(parameters.get("priceElasticity"), weight)
        volume_elasticity = _numeric(parameters.get("volumeElasticity"), 1.0)
        output = source_change * price_elasticity * volume_elasticity
    elif formula == "REVENUE_BRIDGE":
        price = _numeric(parameters.get("priceWeight"), weight)
        volume = _numeric(parameters.get("volumeWeight"), 0.0)
        output = source_change * (price + volume)
    elif formula == "MARGIN_BRIDGE":
        output = source_change * _numeric(parameters.get("marginPassThrough"), weight)
    elif formula == "CAPACITY_UTILIZATION":
        output = source_change * _numeric(parameters.get("utilizationElasticity"), weight)
    elif formula == "INVENTORY_FLOW":
        output = source_change * _numeric(parameters.get("inventoryElasticity"), weight)
    elif formula == "WORKING_CAPITAL":
        output = source_change * _numeric(parameters.get("cashConversionElasticity"), weight)
    elif formula in {"DCF", "PE_MULTIPLE", "EV_EBITDA"}:
        output = source_change * _numeric(parameters.get("valuationSensitivity"), weight)
    elif formula in {"ACCOUNTING_IDENTITY", "CASH_FLOW_IDENTITY", "MARKET_CAP_IDENTITY", "POWER_BALANCE", "FUEL_COST_IDENTITY", "FUEL_COST_BRIDGE"}:
        output = source_change * abs(_numeric(parameters.get("coefficient"), weight))
    elif formula == "EV_EQUITY_BRIDGE":
        output = source_change * abs(_numeric(parameters.get("equitySensitivity"), _numeric(parameters.get("coefficient"), weight)))
    elif formula == "PRICE_BASIS_BRIDGE":
        output = source_change * abs(_numeric(parameters.get("beta"), _numeric(parameters.get("coefficient"), weight)))
    elif formula == "COST_PASS_THROUGH":
        output = source_change * abs(_numeric(parameters.get("passThrough"), _numeric(parameters.get("coefficient"), weight)))
    else:
        output = source_change * weight
    output *= sign
    cap = abs(_numeric(parameters.get("impactCapPct"), 0.0))
    if cap:
        output = max(-cap, min(cap, output))
    return round(output, 6), formula


def simulate_generated_network(scenario_id: str, changes: list[dict[str, Any]], plan: dict[str, Any], metric_values: list[dict[str, Any]], cutoff: str) -> dict[str, Any]:
    nodes, edges = active_graph(plan)
    metric_to_node = {code: node.get("nodeId") for node in nodes for code in node.get("metricCodes", [])}
    node_by_id = {node.get("nodeId"): node for node in nodes}
    impacts: dict[str, float] = {}
    input_nodes: set[str] = set()
    for change in changes:
        code = str(change.get("metricCode") or "")
        target = metric_to_node.get(code) or code
        if target in node_by_id:
            impacts[target] = float(change.get("changePercent") or 0.0)
            input_nodes.add(target)
    if not input_nodes:
        editable = next((node for node in nodes if node.get("editable")), None)
        if editable:
            impacts[editable["nodeId"]] = float(changes[0].get("changePercent") or 0.0) if changes else 0.0
            input_nodes.add(editable["nodeId"])
    structural_types = {"DATA_LINEAGE", "ENTITY_METRIC", "ACCOUNTING_STRUCTURE"}
    simulation_edges = [
        edge for edge in edges
        if edge.get("relationType") not in structural_types
        and edge.get("formulaType") in SUPPORTED_FORMULAS
        and (
            (edge.get("status") == "CONFIRMED" and abs(float(edge.get("weight") or 0)) > 0)
            or (edge.get("candidateSimulation") is True and abs(float(edge.get("candidateWeight") or 0)) > 0)
        )
    ]
    edge_contributions: dict[str, float] = {}
    for _ in range(max(1, len(nodes))):
        progressed = False
        for edge in simulation_edges:
            source = edge.get("sourceNodeId")
            target = edge.get("targetNodeId")
            if source not in impacts:
                continue
            formal_weight = float(edge.get("weight") or 0)
            candidate_weight = float(edge.get("candidateWeight") or 0)
            effective_weight = formal_weight if abs(formal_weight) > 0 else candidate_weight
            output, _ = evaluate_formula(edge.get("formulaType"), impacts[source], effective_weight, str(edge.get("direction") or "positive"), edge.get("formulaParameters"))
            edge_id = str(edge.get("edgeId") or "")
            previous_contribution = edge_contributions.get(edge_id, 0.0)
            delta = output - previous_contribution
            if abs(delta) < 0.000001:
                continue
            edge_contributions[edge_id] = output
            impacts[target] = round(max(-300.0, min(300.0, float(impacts.get(target) or 0) + delta)), 6)
            progressed = True
        if not progressed:
            break
    calculations: list[dict[str, Any]] = []
    for edge in simulation_edges:
        edge_id = str(edge.get("edgeId") or "")
        if edge_id not in edge_contributions:
            continue
        formal_weight = float(edge.get("weight") or 0)
        candidate_weight = float(edge.get("candidateWeight") or 0)
        effective_weight = formal_weight if abs(formal_weight) > 0 else candidate_weight
        _, formula = evaluate_formula(edge.get("formulaType"), impacts.get(edge.get("sourceNodeId"), 0.0), effective_weight, str(edge.get("direction") or "positive"), edge.get("formulaParameters"))
        calculations.append({
            "edgeId": edge.get("edgeId"), "formula": formula, "formulaId": edge.get("formulaId"),
            "inputs": {"sourceChange": impacts.get(edge.get("sourceNodeId"), 0.0), "weight": effective_weight, "direction": edge.get("direction"), "parameters": edge.get("formulaParameters") or {}},
            "output": edge_contributions[edge_id], "lagDays": edge.get("lagDays", 0), "mechanism": edge.get("mechanism"),
            "evidenceClass": "AI_CANDIDATE" if edge.get("candidateSimulation") else "CONFIRMED",
        })
    candidate_used = any(
        edge.get("candidateSimulation") is True
        or edge.get("sourceStatus") == "AI_APPROVED"
        or edge.get("parameterStatus") == "AI_ASSUMPTION"
        for edge in simulation_edges if str(edge.get("edgeId") or "") in edge_contributions
    )
    affected = [{
        "nodeId": node_id, "changePercent": value,
        "confidence": next((float(edge.get("confidence") or 0) for edge in simulation_edges if edge.get("targetNodeId") == node_id), 1.0 if node_id in input_nodes else 0.0),
        "reason": next((edge.get("mechanism") for edge in simulation_edges if edge.get("targetNodeId") == node_id), "用户输入情景"),
    } for node_id, value in impacts.items()]
    return {
        "scenarioId": scenario_id, "status": "CALCULATED" if impacts and simulation_edges else "ABSTAIN",
        "affectedNodes": affected, "affectedEdges": [edge.get("edgeId") for edge in simulation_edges if str(edge.get("edgeId") or "") in edge_contributions],
        "companyResults": [], "summary": ("情景沿 AI 候选关系和参数假设完成条件传播；结果不是正式因果结论。" if candidate_used else "情景沿已确认关系和参数化公式完成确定性传播。") if simulation_edges else "没有可传播的情景关系。",
        "calculationLedger": calculations, "inputChanges": changes,
        "inputDataVersions": sorted({item.get("version") for item in metric_values if item.get("version")}), "dataCutoff": cutoff,
        "usedNodeIds": [node.get("nodeId") for node in nodes], "usedEdges": simulation_edges,
        "formulaVersion": "generic-formula-registry-1.0.0", "parameterVersion": "network-package-parameters",
        "domainPackageVersion": plan.get("networkKind", "MULTI_TABLE_NETWORK"), "companyModelVersion": None,
        "evidenceIds": sorted({item.get("evidenceId") for item in metric_values if item.get("evidenceId")}), "causalStatus": "ABSTAIN" if candidate_used or not simulation_edges else "CONDITIONAL",
        "outputLevel": "CANDIDATE_SCENARIO" if candidate_used else ("SCENARIO_PATH_ONLY" if simulation_edges else "EXPOSURE_ONLY"),
    }

def simulate(scenario_id: str, changes: list[dict[str, Any]], plan: dict[str, Any] | None, metric_values: list[dict[str, Any]], cutoff: str) -> dict[str, Any]:
    if plan and plan.get("mode") == "CREATE_NEW_NETWORK":
        return simulate_generated_network(scenario_id, changes, plan, metric_values, cutoff)
    nodes, edges = active_graph(plan)
    confirmed_edges = [item for item in edges if item.get("status") == "CONFIRMED"]
    shock = next((float(item.get("changePercent", 0)) for item in changes if item.get("metricCode") == "JM_PRICE"), 0.0)
    by_node = {"cokingCoalPrice": shock}
    calculations = []
    for edge in confirmed_edges:
        source_change = by_node.get(edge["sourceNodeId"])
        if source_change is None:
            continue
        sign = -1 if edge["direction"] == "negative" else 1
        output = round(source_change * float(edge["weight"]) * sign, 4)
        by_node[edge["targetNodeId"]] = output
        calculations.append({"edgeId": edge["edgeId"], "formula": "target_change = source_change × direction × weight", "inputs": {"sourceChange": source_change, "direction": edge["direction"], "weight": edge["weight"]}, "output": output, "lagDays": edge["lagDays"]})
    latest = latest_metric_values(metric_values)
    company_results = []
    for node in nodes:
        entity = node.get("entityCode")
        if not entity or node.get("status") == "COMPANY_ADAPTER_REQUIRED":
            continue
        industry_change = by_node.get(node["nodeId"], 0.0)
        model = node.get("companyModel")
        model_change = round(shock * MODEL_FACTORS.get(model, 0.0), 4)
        operating_change = model_change if model else industry_change
        baseline = {code: item for (item_entity, code), item in latest.items() if item_entity == entity}
        revenue = baseline.get("REVENUE")
        net_profit = baseline.get("NET_PROFIT")
        fcf = baseline.get("FREE_CASH_FLOW")
        result = {
            "nodeId": node["nodeId"], "entityCode": entity, "companyName": node["label"], "companyModel": model,
            "changePercent": operating_change, "confidence": 0.68 if revenue else 0.45,
            "baselineRevenue": revenue["value"] if revenue else None,
            "scenarioRevenue": round(revenue["value"] * (1 + operating_change / 100), 2) if revenue else None,
            "baselineNetProfit": net_profit["value"] if net_profit else None,
            "scenarioNetProfit": round(net_profit["value"] * (1 + operating_change * 1.35 / 100), 2) if net_profit else None,
            "baselineFcf": fcf["value"] if fcf else None,
            "scenarioFcf": round(fcf["value"] * (1 + operating_change * 1.2 / 100), 2) if fcf else None,
            "evidenceIds": sorted({item["evidenceId"] for item in baseline.values()}),
            "status": "CALCULATED" if revenue else "DATA_MISSING",
            "reason": f"{model} 使用已同步财务基线和焦煤冲击模型系数计算" if model else "缺少公司模型",
        }
        company_results.append(result)
    affected = [{"nodeId": node_id, "changePercent": value, "confidence": next((edge["confidence"] for edge in confirmed_edges if edge["targetNodeId"] == node_id), 1.0 if node_id == "cokingCoalPrice" else 0.5), "reason": next((edge["mechanism"] for edge in confirmed_edges if edge["targetNodeId"] == node_id), "用户输入情景")} for node_id, value in by_node.items()]
    affected.extend({"nodeId": item["nodeId"], "changePercent": item["changePercent"], "confidence": item["confidence"], "reason": item["reason"]} for item in company_results)
    status = "CALCULATED" if company_results and all(item["status"] == "CALCULATED" for item in company_results) else "PARTIAL"
    return {
        "scenarioId": scenario_id, "status": status, "affectedNodes": affected,
        "affectedEdges": [item["edgeId"] for item in confirmed_edges if item["sourceNodeId"] in by_node],
        "companyResults": company_results, "summary": "焦煤冲击已通过已确认网络和公司专属模型完成确定性计算。",
        "calculationLedger": calculations, "inputChanges": changes,
        "inputDataVersions": sorted({item["version"] for item in metric_values}), "dataCutoff": cutoff,
        "usedNodeIds": [item["nodeId"] for item in nodes], "usedEdges": confirmed_edges,
        "formulaVersion": "coal-steel-deterministic-engine-2.18.0", "parameterVersion": "coal-steel-parameters-1.0.0",
        "domainPackageVersion": "coal-steel-domain-1.0.0", "companyModelVersion": "coal-steel-company-models-1.0.0",
        "evidenceIds": sorted({item["evidenceId"] for item in metric_values}), "causalStatus": "ABSTAIN",
    }
