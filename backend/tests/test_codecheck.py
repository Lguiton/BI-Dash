import pytest

from app.services import autopilot, codecheck, prolab, prolab_cpe  # noqa: F401
from app.services import workroom

need_gcc = pytest.mark.skipif(not codecheck.available()["gcc"], reason="gcc not installed")
need_iv = pytest.mark.skipif(not codecheck.available()["iverilog"], reason="iverilog not installed")

ADDER = """module adder(input [3:0] a, b, output [4:0] s); assign s = a + b; endmodule
module tb; reg [3:0] a, b; wire [4:0] s; adder u(.a(a), .b(b), .s(s));
initial begin a=3; b=4; #1; if (s !== 7) $display("FAIL 3+4=%d", s); else $display("PASS 3+4");
a=15; b=15; #1; if (s !== 30) $display("FAIL 15+15=%d", s); else $display("PASS 15+15"); $finish; end endmodule
"""


@need_iv
def test_verilog_pass_and_fail_are_told_apart():
    assert codecheck.verilog_sim(ADDER)["fail_lines"] == []
    r = codecheck.verilog_sim(ADDER.replace("a + b", "a ^ b"))
    assert r["fail_lines"] and "failing" in r["plain"]


@need_iv
def test_verilog_no_testbench_endless_clock_and_blocked_calls():
    assert "no testbench" in codecheck.verilog_sim("module m(input a, output b); assign b = a; endmodule")["plain"]
    assert codecheck.verilog_sim("module t; reg c=0; always #1 c=~c; endmodule")["timed_out"]
    with pytest.raises(codecheck.CodeError):
        codecheck.verilog_sim('module t; initial $system("echo hi"); endmodule')
    with pytest.raises(codecheck.CodeError):
        codecheck.verilog_sim('`include "/etc/passwd"\nmodule t; endmodule')


@need_iv
def test_syntax_error_is_reported():
    r = codecheck.verilog_sim("module t; assign = ; endmodule")
    assert r["compiled"] is False and "does not compile" in r["plain"]


@need_gcc
def test_c_compile_run_and_memory_fault():
    ok = "#include <stdio.h>\nint main(void){int a[3]={1,2,3};int s=0;for(int i=0;i<3;i++)s+=a[i];printf(\"%d\\n\",s);return 0;}"
    r = codecheck.c_check(ok, run=True)
    assert r["compiled"] and r["stdout"].strip() == "6" and not r["sanitizer_finding"]
    bad = ok.replace("i<3", "i<=3")
    assert codecheck.c_check(bad, run=True)["sanitizer_finding"]
    assert codecheck.c_check("int main( {")["compiled"] is False
    assert codecheck.c_check("int main(void){for(;;);}", run=True)["timed_out"]


@need_gcc
def test_autopilot_only_compiles_c_never_runs_it():
    rep = autopilot.run("x.c", b"#include <stdio.h>\nint main(void){puts(\"hi\");return 0;}\n")
    s = rep["steps"][0]
    assert rep["kind"] == "c_code" and s["status"] == "ran" and "not run" in s["plain"]


@need_iv
def test_autopilot_and_agent_code_blocks_are_verified():
    assert autopilot.run("adder.sv", ADDER.encode())["kind"] == "verilog"
    out = codecheck.verify_blocks("Here you go:\n```verilog\n" + ADDER.replace("a + b", "a ^ b") + "\n```\n")
    assert out and out[0]["status"] == "fail"


def test_missing_tools_give_install_help(monkeypatch):
    monkeypatch.setattr(codecheck, "_tool", lambda n: None)
    with pytest.raises(codecheck.CodeError) as e:
        codecheck.c_check("int main(void){return 0;}")
    assert "apt install" in e.value.message and e.value.status == 501
    with pytest.raises(codecheck.CodeError):
        codecheck.verilog_sim("module m; endmodule")


def test_lab_tools_are_registered():
    ids = {t["id"] for t in prolab._REG["cpe"]["tabs"]}
    assert {"verilog_sim", "c_check"} <= ids
