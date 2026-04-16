import unittest
import pandas as pd
from core.data_parser import DataParser
from core.json_extractor import extract_json_from_response
from workflows.chat import build_chat_context_parts, build_chat_prompt
from workflows.comparison import (
    build_comparison_prompt,
    prepare_comparison_payloads,
    should_summarize,
    summarize_for_llm,
)
from workflows.eda import build_eda_chat_context, build_numeric_summary
from workflows.operating_state import operating_state_to_machine_state
from workflows.audit import calculate_audit_results_from_mapping
from workflows.audit_draft import build_audit_draft
from workflows.evidence import build_evidence_cards_from_literature, select_relevant_evidence_cards
from workflows.measurement_profile import (
    apply_time_column_selection,
    build_measurement_context,
    default_energy_component_columns,
    enhance_mapping_with_supply_ai,
    filter_profile_for_selected_components,
    infer_time_column_with_ai,
    normalize_mapping,
    profile_measurement_dataframe,
    suggest_mapping_locally,
)
from services.export_service import ExportService


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate(self, prompt):
        self.calls.append(prompt)
        return self.response

class TestCoreModules(unittest.TestCase):
    
    def test_data_parser_metrics(self):
        # Mock DataFrame
        df = pd.DataFrame({
            "elapsedTime": [0, 10, 20],
            "Power1": [100, 200, 100],
            "Power2": [50, 50, 50]
        })
        
        details, summary = DataParser.compute_metrics(df, ["Power1", "Power2"])
        
        self.assertIn("Power1", details)
        self.assertEqual(details["Power1"]["mean"], 133.33)
        self.assertEqual(summary["max"], 250.0)
        
    def test_duty_cycle(self):
        df = pd.DataFrame({
            "Power1": [0, 100, 100, 0, 100]
        })
        # Mean is 60, threshold 0.1 * 60 = 6. Active if > 6.
        # 3 out of 5 samples are active = 60%
        cycle = DataParser.calculate_duty_cycle(df, ["Power1"], 60)
        self.assertEqual(cycle, 60.0)

    def test_compute_metrics_handles_irregular_time_axis(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 5, 20],
            "Power1": [100, 100, 200],
        })

        details, summary = DataParser.compute_metrics(df, ["Power1"])

        self.assertEqual(details["Power1"]["total_energy_kWh"], 0.0008)
        self.assertEqual(summary["total_energy_kWh"], 0.0008)

    def test_compute_metrics_empty_group(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 10],
            "Other": [1, 2],
        })

        details, summary = DataParser.compute_metrics(df, ["Missing"])

        self.assertEqual(details, {})
        self.assertEqual(summary, {})

    def test_compute_metrics_missing_time_column(self):
        df = pd.DataFrame({"Power1": [100, 200]})

        with self.assertRaises(ValueError):
            DataParser.compute_metrics(df, ["Power1"])

    def test_extract_json_from_raw_json(self):
        self.assertEqual(extract_json_from_response('{"a": 1}'), {"a": 1})

    def test_extract_json_from_code_block(self):
        response = '```json\n{"a": 1}\n```'
        self.assertEqual(extract_json_from_response(response), {"a": 1})

    def test_extract_json_rejects_invalid_json(self):
        with self.assertRaises(ValueError):
            extract_json_from_response("not json")

    def test_comparison_summary_helpers(self):
        data = {
            "metadata": {"machine_name": "M1"},
            "Overall Summary": {"Total Energy (kWh)": 1.2},
            "Elektrisch": {"Total Elektrisch": {"mean": 10}},
            "Pneumatisch": {"Total Pneumatisch": {"mean": 5}},
        }

        summary = summarize_for_llm(data)

        self.assertTrue(should_summarize(2, 3))
        self.assertEqual(summary["Electrical Total"], {"mean": 10})
        self.assertEqual(summary["Pneumatic Total"], {"mean": 5})

    def test_prepare_comparison_payloads_keeps_full_data_for_small_matrix(self):
        audits = {"audit.json": {"raw": True}}
        benchmarks = {"Paper": {"raw": True}}

        audit_payload, benchmark_payload = prepare_comparison_payloads(audits, benchmarks, use_summary=False)

        self.assertEqual(audit_payload, audits)
        self.assertEqual(benchmark_payload, benchmarks)

    def test_chat_prompt_helpers(self):
        parts = build_chat_context_parts({"audit.json": {"x": 1}}, {"Paper": {"y": 2}})
        prompt = build_chat_prompt("Question?", parts)

        self.assertIn("### AUDIT DATA ###", parts)
        self.assertIn("CONTEXT INFORMATION", prompt)
        self.assertIn("USER QUESTION: Question?", prompt)

    def test_chat_prompt_without_context(self):
        self.assertEqual(build_chat_prompt("Question?", []), "Question?")

    def test_chat_context_accepts_uploaded_eda_without_benchmarks(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 1, 2],
            "Power_W": [100, 120, 110],
        })
        profile = profile_measurement_dataframe(df)
        summary = build_numeric_summary(df, profile)
        eda_context = build_eda_chat_context("sample.csv", df, profile, summary)

        parts = build_chat_context_parts({}, {}, [eda_context])
        prompt = build_chat_prompt("What stands out?", parts)

        self.assertIn("### UPLOADED DATASET ###", prompt)
        self.assertIn("Power_W", prompt)

    def test_comparison_prompt_accepts_analysis_context(self):
        prompt = build_comparison_prompt(
            {"audit.json": {"Overall Summary": {"Total Energy (kWh)": 1.2}}},
            {"Paper": {"energy_data": {"energy_usage": "1.0 kWh"}}},
            "Focus on pneumatic losses.",
        )

        self.assertIn("Additional analysis focus", prompt)
        self.assertIn("Focus on pneumatic losses.", prompt)

    def test_operating_state_mapping(self):
        expected = {
            "Standby": "Idle",
            "Ready": "Idle",
            "E-Stop": "Idle",
            "Processing": "Cutting",
            "Off": "Maintenance",
        }

        for operating_state, machine_state in expected.items():
            self.assertEqual(operating_state_to_machine_state(operating_state), machine_state)

    def test_measurement_profile_detects_time_and_sampling_rate(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 0.5, 1.0],
            "Kuehlung_kW": [1.0, 1.2, 1.1],
        })

        profile = profile_measurement_dataframe(df)

        self.assertEqual(profile["time_column"], "elapsedTime")
        self.assertEqual(profile["sampling_rate_hz"], 2.0)
        self.assertEqual(profile["time_column_source"], "local_name_hint")
        self.assertEqual(profile["columns"][1]["suggested_unit"], "kW")

    def test_time_column_ai_fallback_selects_existing_column(self):
        df = pd.DataFrame({
            "CycleNo": [3, 1, 2],
            "t_axis": [0.0, 0.5, 1.0],
            "Hauptversorgung": [100, 120, 110],
        })
        profile = profile_measurement_dataframe(df)
        context = build_measurement_context(df, profile)
        provider = FakeProvider('{"time_column": "t_axis", "confidence": 0.82, "rationale": "monotonic seconds"}')

        result = infer_time_column_with_ai(provider, profile, context)
        updated = apply_time_column_selection(profile, df, result["time_column"], result["source"], result["confidence"], result["rationale"])

        self.assertEqual(result["time_column"], "t_axis")
        self.assertEqual(updated["sampling_rate_hz"], 2.0)

    def test_time_column_ai_fallback_rejects_invalid_response(self):
        df = pd.DataFrame({
            "sample": [3, 1, 2],
            "Power": [100, 120, 110],
        })
        profile = profile_measurement_dataframe(df)
        context = build_measurement_context(df, profile)
        provider = FakeProvider("not json")

        result = infer_time_column_with_ai(provider, profile, context)

        self.assertEqual(result["error"], "parse_failed")

    def test_measurement_profile_ignores_boolean_columns_for_power_mapping(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 1, 2],
            "DoorClosed": [True, True, False],
            "Power_W": [100, 120, 130],
        })

        profile = profile_measurement_dataframe(df)
        mapping = suggest_mapping_locally(profile)

        bool_column = next(column for column in profile["columns"] if column["name"] == "DoorClosed")
        self.assertFalse(bool_column["is_numeric"])
        self.assertEqual(bool_column["suggested_unit"], "unknown")
        self.assertNotIn("DoorClosed", {channel["source_column"] for channel in mapping["channels"]})

    def test_default_component_selection_excludes_temperature(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 1, 2],
            "Hauptversorgung": [100, 120, 110],
            "Antriebe": [40, 45, 42],
            "AirPower_Hauptversorgung": [20, 20, 20],
            "Temperatur Außen": [21.0, 21.5, 21.7],
            "CycleID": [1, 2, 3],
        })
        profile = profile_measurement_dataframe(df)

        selected = default_energy_component_columns(profile)

        self.assertIn("Hauptversorgung", selected)
        self.assertIn("Antriebe", selected)
        self.assertIn("AirPower_Hauptversorgung", selected)
        self.assertNotIn("Temperatur Außen", selected)
        self.assertNotIn("CycleID", selected)

    def test_filtered_profile_blocks_unselected_mapping_columns(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 1, 2],
            "Hauptversorgung": [100, 120, 110],
            "Temperatur Außen": [21.0, 21.5, 21.7],
        })
        profile = profile_measurement_dataframe(df)
        filtered = filter_profile_for_selected_components(profile, ["Hauptversorgung"])

        mapping = normalize_mapping({
            "time_column": "elapsedTime",
            "channels": [
                {"source_column": "Hauptversorgung", "canonical_name": "Hauptversorgung", "medium": "electric", "unit": "W"},
                {"source_column": "Temperatur Außen", "canonical_name": "Temperatur", "medium": "electric", "unit": "W"},
            ],
        }, filtered)

        self.assertEqual({channel["source_column"] for channel in mapping["channels"]}, {"Hauptversorgung"})
        self.assertIn("Temperatur Außen", mapping["component_selection"]["excluded_numeric_columns"])

    def test_local_mapping_and_mapped_audit(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 10, 20],
            "AirPower_Blum": [1, 1, 1],
            "Kuehlung_kW": [2, 2, 2],
        })
        profile = profile_measurement_dataframe(df)
        mapping = normalize_mapping(suggest_mapping_locally(profile), profile)

        result = calculate_audit_results_from_mapping(
            df,
            mapping,
            {
                "machine_name": "CNC",
                "operator": "Admin",
                "machine_state": "Cutting",
                "material": "Aluminum",
            },
        )

        self.assertIn("Pneumatisch", result)
        self.assertGreater(result["Overall Summary"]["Total Energy (kWh)"], 0)
        self.assertTrue(result["Overall Summary"]["Top Variables"])

    def test_mapped_audit_stores_operating_and_machine_state(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 10, 20],
            "Power_W": [100, 100, 100],
        })
        profile = profile_measurement_dataframe(df)
        mapping = normalize_mapping(suggest_mapping_locally(profile), profile)

        result = calculate_audit_results_from_mapping(
            df,
            mapping,
            {
                "machine_name": "CNC",
                "operator": "Admin",
                "machine_state": operating_state_to_machine_state("Processing"),
                "operating_state": "Processing",
                "material": "Aluminum",
            },
        )

        self.assertEqual(result["metadata"]["operating_state"], "Processing")
        self.assertEqual(result["metadata"]["machine_state"], "Cutting")

    def test_local_mapping_detects_main_supplies(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 1, 2],
            "Hauptversorgung": [100, 100, 100],
            "Antriebe": [30, 30, 30],
            "AirPower_Hauptversorgung": [50, 50, 50],
            "AirPower_Blum": [5, 5, 5],
        })
        profile = profile_measurement_dataframe(df)
        mapping = suggest_mapping_locally(profile)

        balance_sources = {
            channel["source_column"]
            for channel in mapping["channels"]
            if channel["is_balance_source"]
        }

        self.assertIn("Hauptversorgung", balance_sources)
        self.assertIn("AirPower_Hauptversorgung", balance_sources)

    def test_supply_ai_fallback_marks_missing_main_supply(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 1, 2],
            "LineA": [100, 100, 100],
            "Drive": [30, 30, 30],
        })
        profile = profile_measurement_dataframe(df)
        mapping = normalize_mapping({
            "time_column": "elapsedTime",
            "channels": [
                {"source_column": "LineA", "canonical_name": "Line A", "medium": "electric", "unit": "W", "confidence": 0.5},
                {"source_column": "Drive", "canonical_name": "Drive", "medium": "electric", "unit": "W", "confidence": 0.5},
            ],
        }, profile)
        provider = FakeProvider('{"electric_main_supply": {"source_column": "LineA", "confidence": 0.8, "rationale": "upstream feed"}, "pneumatic_main_supply": null}')

        enhanced = enhance_mapping_with_supply_ai(provider, mapping, profile, build_measurement_context(df, profile))

        line = next(channel for channel in enhanced["channels"] if channel["source_column"] == "LineA")
        self.assertTrue(line["is_balance_source"])
        self.assertEqual(line["supply_role"], "main_supply")

    def test_mapped_audit_avoids_double_counting_main_supplies(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 3600],
            "Hauptversorgung": [1000, 1000],
            "Antriebe": [400, 400],
            "AirPower_Hauptversorgung": [500, 500],
            "AirPower_Blum": [100, 100],
        })
        profile = profile_measurement_dataframe(df)
        mapping = normalize_mapping(suggest_mapping_locally(profile), profile)

        result = calculate_audit_results_from_mapping(
            df,
            mapping,
            {
                "machine_name": "CNC",
                "operator": "Admin",
                "machine_state": "Cutting",
                "material": "Aluminum",
            },
        )

        self.assertEqual(result["Overall Summary"]["Total Energy (kWh)"], 1.5)
        self.assertEqual(result["balance"]["electric_source"], "Hauptversorgung")
        self.assertEqual(result["balance"]["pneumatic_source"], "AirPower_Hauptversorgung")
        self.assertNotIn("Hauptversorgung", result["Overall Summary"]["Top Variables"])

    def test_mapped_audit_ignores_channels_not_included_in_audit(self):
        df = pd.DataFrame({
            "elapsedTime": [0, 3600],
            "Hauptversorgung": [1000, 1000],
            "Temperature_C": [25, 26],
        })
        profile = profile_measurement_dataframe(df)
        mapping = normalize_mapping({
            "time_column": "elapsedTime",
            "channels": [
                {
                    "source_column": "Hauptversorgung",
                    "canonical_name": "Hauptversorgung",
                    "medium": "electric",
                    "unit": "W",
                    "include_in_audit": True,
                },
                {
                    "source_column": "Temperature_C",
                    "canonical_name": "Temperature",
                    "medium": "electric",
                    "unit": "W",
                    "include_in_audit": False,
                },
            ],
        }, profile)

        result = calculate_audit_results_from_mapping(
            df,
            mapping,
            {
                "machine_name": "CNC",
                "operator": "Admin",
                "machine_state": "Cutting",
                "material": "Aluminum",
            },
        )

        self.assertEqual(result["Overall Summary"]["Total Energy (kWh)"], 1.0)
        self.assertNotIn("Temperature", result["Elektrisch"]["Variables"])

    def test_evidence_cards_and_audit_draft(self):
        literature = [{
            "paper_metadata": {
                "title": "Milling energy paper",
                "authors": ["A"],
                "publication_date": "2024",
            },
            "machine_info": {
                "machine_type": "milling machine",
                "material_processed": "Aluminum",
            },
            "energy_data": {"energy_usage": "10 kWh"},
            "kpi_metrics": {"efficiency": "high auxiliary demand"},
        }]
        audit_results = {
            "metadata": {"machine_name": "CNC_Milling_1", "duration_seconds": 20, "material": "Aluminum"},
            "mapping": {"time_column": "elapsedTime", "channels": [{"confidence": 0.8}]},
            "Overall Summary": {
                "Total Energy (kWh)": 1,
                "Mean Power (W)": 100,
                "Energy Rate (kWh/hour)": 12,
                "Top Variables": {"Kuehlung": 0.8},
            },
        }

        cards = build_evidence_cards_from_literature(literature)
        selected = select_relevant_evidence_cards(audit_results, cards)
        draft = build_audit_draft(audit_results, selected, "Manual note")

        self.assertTrue(cards)
        self.assertTrue(selected)
        self.assertIn("traffic_lights", draft)
        self.assertEqual(draft["manual_notes"], "Manual note")
        self.assertTrue(any(measure["category"] == "Retrofit-Potenzial" for measure in draft["recommended_measures"]))
        self.assertTrue(any(measure["category"] == "Betriebspotenzial" for measure in draft["recommended_measures"]))

    def test_management_pdf_builds_with_extended_sections(self):
        audit_results = {
            "metadata": {"machine_name": "CNC", "duration_seconds": 3600, "material": "Aluminum"},
            "mapping": {"time_column": "elapsedTime", "sampling_rate_hz": 1, "channels": []},
            "balance": {"electric_total_kWh": 1.0, "pneumatic_total_kWh": 0.5, "total_energy_kWh": 1.5},
            "component_analysis": {"coverage_vs_main_supply_pct": {"electric": 40, "pneumatic": 20}},
            "Elektrisch": {"Variables": {}, "Total Elektrisch": {"total_energy_kWh": 1.0}},
            "Pneumatisch": {"Variables": {}, "Total Pneumatisch": {"total_energy_kWh": 0.5}},
            "Overall Summary": {
                "Total Energy (kWh)": 1.5,
                "Mean Power (W)": 1500,
                "Energy Rate (kWh/hour)": 1.5,
                "Top Variables": {"Antriebe": 0.4},
            },
        }
        draft = build_audit_draft(audit_results, [], "Manual note")

        pdf = ExportService.create_management_audit_report(audit_results, draft)

        self.assertGreater(len(pdf.getvalue()), 1000)

    def test_evidence_cards_accept_list_machine_info(self):
        literature = [{
            "paper_metadata": {
                "title": "Multi-machine milling paper",
                "authors": ["A"],
                "publication_date": "2024",
            },
            "machine_info": [
                {
                    "maschine_name": "Machine A",
                    "maschine_type": "3-axis vertical milling machine",
                },
                {
                    "maschine_name": "Machine B",
                    "maschine_type": "3-axis vertical milling machine",
                },
            ],
            "material_processed": "Aluminum 6082",
            "energy_data": {"energy_usage": "10 kWh"},
            "kpi_metrics": {},
        }]

        cards = build_evidence_cards_from_literature(literature)

        self.assertEqual(cards[0]["machine_type"], "3-axis vertical milling machine")
        self.assertEqual(cards[0]["material"], "Aluminum 6082")

if __name__ == "__main__":
    unittest.main()

