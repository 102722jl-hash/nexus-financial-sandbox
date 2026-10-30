from types import SimpleNamespace

import v218_pipeline
from db_connectors import _mysql_identifier as profile_mysql_identifier, apply_sample_profile, identifier, profile_rows, table_adapters
from v218_pipeline import (
    _mapping_by_table,
    _mysql_date_expression,
    _mysql_identifier,
    _postgres_rows,
    build_network_plan,
    rule_candidates,
    sync_database,
    table_adapter_candidates,
)


assert identifier("财务数据", "table") == "财务数据"
assert identifier("2026年一季报", "table") == "2026年一季报"
assert identifier("公司.日报", "table") == "公司.日报"
for invalid in ("", "坏\x00表", "坏\n表"):
    try:
        identifier(invalid, "table")
        raise AssertionError("invalid identifier accepted")
    except ValueError:
        pass

profile = profile_rows(
    [("研究.schema", "2026年一季报.财务", "营业收入.含税", "numeric")],
    "客户数据库",
)
locator = profile[0]["sourceLocator"]
assert locator == {
    "database": "客户数据库",
    "schema": "研究.schema",
    "table": "2026年一季报.财务",
    "column": "营业收入.含税",
}

date_candidate = rule_candidates(
    profile_rows([("财务", "利润表", "公告日期", "date")], "客户数据库"),
    "SOURCE-UNICODE",
)[0]
assert date_candidate["metricCode"] == "ANNOUNCEMENT_DATE"
assert date_candidate["sourceLocator"]["column"] == "公告日期"


def mapping(code, column):
    return {
        "mappingId": "MAP-" + code,
        "status": "CONFIRMED",
        "metricCode": code,
        "sourceField": f"客户数据库.研究.schema.2026年一季报.财务.{column}",
        "sourceLocator": {
            "database": "客户数据库",
            "schema": "研究.schema",
            "table": "2026年一季报.财务",
            "column": column,
        },
    }


mappings = [
    mapping("ENTITY_CODE", "公司.代码"),
    mapping("REPORT_PERIOD", "报告.期间"),
    mapping("ANNOUNCEMENT_DATE", "公告.日期"),
    mapping("OPDATE", "版本.时间"),
    mapping("REVENUE", "营业收入.含税"),
]
grouped = _mapping_by_table(mappings, "public", "客户数据库")
assert list(grouped) == [("研究.schema", "2026年一季报.财务")]
table_mappings = next(iter(grouped.values()))
assert [item["column"] for item in table_mappings] == [
    "公司.代码",
    "报告.期间",
    "公告.日期",
    "版本.时间",
    "营业收入.含税",
]

wrong_database = [{**mappings[0], "sourceLocator": {**mappings[0]["sourceLocator"], "database": "其他数据库"}}]
try:
    _mapping_by_table(wrong_database, "public", "客户数据库")
    raise AssertionError("cross-database mapping accepted")
except ValueError as error:
    assert str(error).startswith("MAPPING_DATABASE_MISMATCH:")

assert _mysql_identifier("财务\u0060日报", "table") == "\u0060财务\u0060\u0060日报\u0060"
assert _mysql_identifier("净利率(%)", "column") == "\u0060净利率(%%)\u0060"
assert profile_mysql_identifier("净利率(%)", "column") == "\u0060净利率(%%)\u0060"
mysql_date = _mysql_date_expression(["公告.日期"])
assert "LEFT(" in mysql_date and "\u0060公告.日期\u0060" in mysql_date


class FakeCursor:
    description = []

    @staticmethod
    def fetchall():
        return []


class FakeConnection:
    def __init__(self):
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        if query == "SHOW transaction_read_only":
            return SimpleNamespace(fetchone=lambda: ("on",))
        if not isinstance(query, str):
            self.query = query
            self.params = params
            return FakeCursor()
        return SimpleNamespace()

    @staticmethod
    def rollback():
        return None


fake = FakeConnection()
original_connect = v218_pipeline.psycopg.connect
v218_pipeline.psycopg.connect = lambda **_: fake
try:
    rows = _postgres_rows(
        {"type": "postgresql", "host": "localhost", "database": "客户数据库", "user": "reader"},
        "研究.schema",
        "2026年一季报.财务",
        table_mappings,
        "2026-05-08",
        ["600019.SH"],
        50,
        0,
    )
finally:
    v218_pipeline.psycopg.connect = original_connect

assert rows == []
rendered = fake.query.as_string(None)
for quoted in (
    '"研究.schema"',
    '"2026年一季报.财务"',
    '"公司.代码"',
    '"报告.期间"',
    '"公告.日期"',
    '"版本.时间"',
    '"营业收入.含税"',
):
    assert quoted in rendered
assert "LEFT(regexp_replace" in rendered
assert "CAST(\"公司.代码\" AS TEXT) = ANY(%s)" in rendered
assert fake.params == ["20260508", "20260508", ["600019.SH"], 50, 0]

custom_profile = profile_rows(
    [
        ("workspace", "fr传媒_2022方法1", "股票代码", "character varying"),
        ("workspace", "fr传媒_2022方法1", "股票简称", "character varying"),
        ("workspace", "fr传媒_2022方法1", "得分", "double precision"),
        ("workspace", "fr传媒_2022方法1", "成长能力", "numeric"),
    ],
    "workspace",
)
text_numeric_profile = profile_rows([("workspace", "fr传媒_2024", "得分", "text")], "workspace")
apply_sample_profile(text_numeric_profile, "fr传媒_2024", [("88.5",), ("91",), ("--",), (None,)])
assert text_numeric_profile[0]["numericSampleRate"] == 0.6667
apply_sample_profile(text_numeric_profile, "fr传媒_2024", [("88.5",), ("91",), ("76%",), (None,)])
assert text_numeric_profile[0]["numericSampleRate"] == 1.0
assert rule_candidates(text_numeric_profile, "SOURCE-TEXT-NUMERIC", "CREATE_NEW_NETWORK")[0]["candidateSource"] == "CUSTOM_NUMERIC"
coal_like = profile_rows([("workspace", "行业数据", "coking_coal_price", "numeric")], "workspace")
assert rule_candidates(coal_like, "SOURCE-NEW", "CREATE_NEW_NETWORK")[0]["candidateSource"] == "CUSTOM_NUMERIC"
assert rule_candidates(coal_like, "SOURCE-EXTEND", "EXTEND_EXISTING")[0]["metricCode"] == "JM_PRICE"
adapters = table_adapters("workspace", "workspace", ["fr传媒_2022方法1"], custom_profile)
assert adapters[0]["reportPeriodHint"] == "20221231"
assert adapters[0]["reportPeriodSource"] == "INFERRED_FROM_TABLE_NAME"
custom_candidates = rule_candidates(custom_profile, "SOURCE-CUSTOM")
custom_candidates += table_adapter_candidates(adapters, custom_candidates, "SOURCE-CUSTOM")
assert {item["metricCode"] for item in custom_candidates if item["candidateSource"] == "CUSTOM_NUMERIC"} == {
    item["metricCode"] for item in custom_candidates if item["columnName"] in {"得分", "成长能力"}
}
assert any(item.get("valueMode") == "CONSTANT" and item["metricCode"] == "REPORT_PERIOD" for item in custom_candidates)
assert any(item.get("valueMode") == "SYNC_CUTOFF" and item["metricCode"] == "ANNOUNCEMENT_DATE" for item in custom_candidates)
confirmed_custom = [{**item, "status": "CONFIRMED"} for item in custom_candidates if item["metricCode"] != "UNRESOLVED"]
original_rows = v218_pipeline._postgres_rows
v218_pipeline._postgres_rows = lambda *_args, **_kwargs: [{
    "股票代码": "300027.SZ",
    "股票简称": "华谊兄弟",
    "得分": 87.5,
    "成长能力": 73.2,
}]
try:
    custom_sync = sync_database(
        {"type": "postgresql", "host": "localhost", "database": "workspace", "schema": "workspace", "user": "reader"},
        confirmed_custom,
        "SOURCE-CUSTOM",
        "2026-05-08",
        [],
        100,
    )
finally:
    v218_pipeline._postgres_rows = original_rows
assert custom_sync["metricValuesCreated"] == 2
assert {item["metricName"] for item in custom_sync["metricValues"]} == {"得分", "成长能力"}
assert all(item["entityCode"] == "300027.SZ" and item["entityName"] == "华谊兄弟" for item in custom_sync["metricValues"])
assert all(item["reportPeriod"] == "20221231" and item["announcementDate"] == "2026-05-08" for item in custom_sync["metricValues"])
assert all(item["temporalBasis"] == "SYNC_CUTOFF_ASSUMPTION" and not item["historicalReplayEligible"] for item in custom_sync["metricValues"])
custom_plan = build_network_plan("SOURCE-CUSTOM", custom_sync["metricValues"], "generated-financial", "CREATE_NEW_NETWORK", "传媒评分网络")
assert custom_plan["networkKind"] == "SOURCE_DEFINED_NETWORK"
assert [item["label"] for item in custom_plan["layerLabels"]] == ["数据范围 / 时间", "市场与成长", "运营与效率", "资本与风险", "结果与质量", "公司 / 数据实体"]
assert any(node["label"] == "得分" for node in custom_plan["graph"]["nodes"])
assert any(node["label"] == "华谊兄弟" for node in custom_plan["graph"]["nodes"])
assert any(edge["relationType"] == "ENTITY_METRIC" for edge in custom_plan["graph"]["edges"])

no_entity_profile = profile_rows(
    [("workspace", "fr传媒_fr2024", "得分(%)", "varchar")],
    "workspace",
)
apply_sample_profile(no_entity_profile, "fr传媒_fr2024", [("88.5%",), ("76",)])
no_entity_candidates = rule_candidates(no_entity_profile, "SOURCE-ROW-HASH", "CREATE_NEW_NETWORK")
no_entity_adapters = table_adapters("workspace", "workspace", ["fr传媒_fr2024"], no_entity_profile)
no_entity_candidates += table_adapter_candidates(no_entity_adapters, no_entity_candidates, "SOURCE-ROW-HASH", "CREATE_NEW_NETWORK")
row_hash = next(item for item in no_entity_candidates if item.get("valueMode") == "ROW_HASH")
assert row_hash["metricCode"] == "ENTITY_CODE"
confirmed_no_entity = [{**item, "status": "CONFIRMED"} for item in no_entity_candidates]
original_rows = v218_pipeline._postgres_rows
v218_pipeline._postgres_rows = lambda *_args, **_kwargs: [{"得分(%)": "88.5"}, {"得分(%)": "76"}]
try:
    no_entity_sync = sync_database(
        {"type": "postgresql", "host": "localhost", "database": "workspace", "schema": "workspace", "user": "reader"},
        confirmed_no_entity,
        "SOURCE-ROW-HASH",
        "2026-05-08",
        [],
        100,
    )
finally:
    v218_pipeline._postgres_rows = original_rows
assert no_entity_sync["metricValuesCreated"] == 2
assert len({item["entityCode"] for item in no_entity_sync["metricValues"]}) == 2
grouped_no_entity = _mapping_by_table(confirmed_no_entity, "workspace", "workspace")
fake_no_entity = FakeConnection()
v218_pipeline.psycopg.connect = lambda **_: fake_no_entity
try:
    _postgres_rows(
        {"type": "postgresql", "host": "localhost", "database": "workspace", "user": "reader"},
        "workspace",
        "fr传媒_fr2024",
        next(iter(grouped_no_entity.values())),
        "2026-05-08",
        [],
        50,
        0,
    )
finally:
    v218_pipeline.psycopg.connect = original_connect
assert "ROW_NUMBER()" not in fake_no_entity.query.as_string(None)
assert '"得分(%)"' in fake_no_entity.query.as_string(None)
assert fake_no_entity.params == [50, 0]
mysql_parameterized = "SELECT " + _mysql_identifier("净利率(%)", "column") + " LIMIT %s"
assert (mysql_parameterized % (50,)) == "SELECT `净利率(%)` LIMIT 50"

print("V2.19 custom table adapter tests: 52/52 passed")
