import bud_proto as P


def test_heartbeat_populates_state():
    st = P.TamaState()
    P.parse_line('{"total":8,"running":1,"waiting":0,"tokens":97000,'
                 '"tokens_today":241000,"msg":"git push"}', st)
    assert (st.total, st.running, st.waiting) == (8, 1, 0)
    assert st.tokens == 97000 and st.tokens_today == 241000
    assert st.msg == "git push"


def test_status_poll_returns_ack_with_uptime():
    st = P.TamaState()
    reply = P.parse_line('{"cmd":"status"}', st, uptime=42)
    assert reply is not None and '"ack":"status"' in reply
    assert '"up":42' in reply and '"name":"Claude-PyPortal"' in reply


def test_prompt_set_and_clear():
    st = P.TamaState()
    P.parse_line('{"total":1,"running":0,"waiting":1,'
                 '"prompt":{"id":"req_1","tool":"Bash","hint":"rm -rf x"}}', st)
    assert (st.prompt_id, st.prompt_tool, st.prompt_hint) == ("req_1", "Bash", "rm -rf x")
    P.parse_line('{"total":1,"running":0,"waiting":0}', st)
    assert st.prompt_id == ""


def test_entries_bump_line_gen_only_on_change():
    st = P.TamaState()
    P.parse_line('{"total":1,"entries":["a","b"]}', st)
    g1 = st.line_gen
    P.parse_line('{"total":1,"entries":["a","b"]}', st)   # unchanged
    assert st.line_gen == g1
    P.parse_line('{"total":1,"entries":["a","b","c"]}', st)  # changed
    assert st.line_gen == g1 + 1


def test_permission_cmd_format():
    assert P.permission_cmd("req_9", "once") == \
        '{"cmd":"permission","id":"req_9","decision":"once"}'
    assert P.permission_cmd("req_9", "deny") == \
        '{"cmd":"permission","id":"req_9","decision":"deny"}'


def test_owner_and_name_commands():
    st = P.TamaState()
    assert '"ack":"owner"' in P.parse_line('{"cmd":"owner","name":"Shai"}', st)
    assert st.owner_pending == "Shai"
    assert '"ack":"name"' in P.parse_line('{"cmd":"name","name":"Clawd"}', st)
    assert st.name_pending == "Clawd"
