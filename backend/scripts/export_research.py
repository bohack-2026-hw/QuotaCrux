"""Export representative research runs as deliverable bundles into docs/research/, with an index.

    uv run python scripts/export_research.py

Runs are chosen by rule, not by hand-picked ids: each case shows one thing the Research Agent PRD asks to see,
including a run without improvement and a run whose final test failed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from routeevo import cli, compare, db, narrative, report

OUT = Path(__file__).resolve().parents[2] / "docs" / "research"


def learn_run(task: str) -> str:
    return db.one("SELECT run_id FROM runs WHERE mode = 'learn' AND task_id = ? AND json_extract(config_json, '$.label') = 'formal A learning'",
                  (task,))["run_id"]


def comparison_runs(prefix: str) -> dict:
    row = next(r for r in db.all_rows("SELECT comparison_id, label FROM comparisons ORDER BY created_at DESC") if (r["label"] or "").startswith(prefix))
    return compare.summarize(row["comparison_id"])


def pick_cases() -> list[tuple[str, str, str]]:
    c = comparison_runs("C final")
    new = c["snapshot_b"]
    cases = [(learn_run("A-01"), "反馈驱动的修正链",
              "Qwen 的第一个假设被实测反驳（0.90×），第二个候选输出格式错误；连续两次未达标触发升级，GPT 读到具体失败反馈后提出新假设并得到支持。"),
             (learn_run("A-05"), "没有验证出改进",
              "高基数工作负载上 Qwen 两个、GPT 一个候选都正确但更慢（0.80—0.83×），三个假设均被反驳；预算耗尽后交付初始程序，结论是“没有验证出改进”，三条无收益经验写入下一版本。")]
    # a held-out run that read experience and reached the goal with a single request
    one_shot = next((r for t in c["tasks"] for r in c["per_task"][t][new]["runs"]
                     if r["goal_met"] and r["model_requests"] == 1 and r["experiences_read"]), None)
    if one_shot:
        cases.append((one_shot["run_id"], "读取经验后一次达标",
                      f"C 最终留出任务、读取 {new}：Qwen 读到匹配的成功经验，第一次提交的候选即通过验证并达标。"))
    # a run that met the goal on dev data but whose frozen candidate failed the final test's strict rule
    missed = next((r for t in c["tasks"] for s in (c["snapshot_a"], new) for r in c["per_task"][t][s]["runs"]
                   if r["stop_reason"] == "goal_reached" and not r["goal_met"]), None)
    if missed:
        cases.append((missed["run_id"], "开发达标、最终测试未达标",
                      "开发数据上已达标并停止；冻结候选在隐藏最终数据上正确，但有一个计时样本不快于基线，按规则如实记为未达标。"))
    return cases


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    rows = ["# 研究成果样例", "",
            "由 `backend/scripts/export_research.py` 按规则从正式运行中选出并导出，每个目录是一份完整交付："
            "研究记录（`README.md`：研究任务、过程、假设与实验、最终测试、资源、复现）、最佳程序 `best.py`、全部候选、"
            "原始模型请求与回复 `model_calls/`、结构化报告 `report.json` 和复核脚本 `reproduce.sh`。"
            "任意一次运行都可以用 `uv run routeevo export-run <run_id> --bundle <目录>` 导出。", "",
            "| 案例 | 任务 · 读取快照 | 结论 | 请求 · 费用 | 说明 |", "|---|---|---|---|---|"]
    for run_id, title, why in pick_cases():
        rep = report.build(run_id)
        cli.export_bundle(run_id, OUT / run_id, narrative.run_markdown(run_id))
        u = rep["usage"]["total"]
        rows.append(f"| [{title}]({run_id}/README.md) | {rep['task']['task_id']} · {rep['snapshot_id']} | {rep['outcome']['summary']} | "
                    f"{rep['iterations']['model_requests']} 次 · {'$%.3f' % u['cost_usd'] if u['cost_usd'] is not None else '未知'} | {why} |")
    (OUT / "README.md").write_text("\n".join(rows) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
