import pytest
from app.services import ml_concepts as mc, nlp_lab as nl, nn_lab as nn


def test_neuron_and_params():
    r = nn.neuron([1, 0, 1], [5, 3, 2], 5)
    assert r["z"] == 2 and r["decision"] is True
    assert nn.parameter_count([3, 4, 1])["parameters"] == 21
    assert nn.parameter_count([2, 3, 3, 1])["deep"] is True and nn.parameter_count([3, 4, 1])["deep"] is False
    with pytest.raises(nn.NnError):
        nn.neuron([1], [1, 2], 0)


def test_xor_needs_hidden_layer():
    assert nn.train_mlp("xor", [], "tanh", 1500, 0.5)["accuracy"] < 1
    r = nn.train_mlp("xor", [4], "tanh", 2000, 0.5)
    assert r["accuracy"] == 1 and r["loss_curve"][-1]["loss"] < r["loss_curve"][0]["loss"]
    assert nn.train_mlp("and", [], "tanh", 1000, 0.5)["accuracy"] == 1
    with pytest.raises(nn.NnError):
        nn.train_mlp("xor", [99])


def test_convolve():
    r = nn.convolve("square", "vertical_edges")
    assert len(r["output"]) == 6 and max(max(x) for x in r["output"]) > 0
    assert nn.convolve("square", "identity")["output"][1][1] == 9


def test_ml_concepts():
    r = mc.learn_rules()
    assert r["synthetic"] and {s["set"] for s in r["scores"]} == {"training", "validation", "test"} and "class:" in r["rules"]
    assert mc.split_sizes(1000)["test"] == 200
    with pytest.raises(mc.MlcError):
        mc.split_sizes(1000, 50, 20, 20)
    m = mc.metrics(5, 5, 45, 945)
    assert m["accuracy"] == 0.95 and m["recall"] == 0.1 and m["notes"]
    k = mc.kmeans()
    assert sorted(k["sizes"]) == [25, 25, 25]
    q = mc.q_learning()
    assert q["reaches_goal"] and q["avg_reward_last_tenth"] > q["avg_reward_first_tenth"]
    assert mc.rpa_fit(1, 1, 1, 1, 1, 1000, 5)["verdict"] == "good" and mc.rpa_fit(0, 0, 1, 0, 0, 1, 1)["verdict"] == "poor"
    assert "RAG" in mc.choose_approach("answer", "none", "small", False, True)["pick"]
    assert mc.thermostat(proactive=True)["mode"] == "proactive"
    ref = mc.reference()
    assert ref["slips"] and ref["not_built"] and len(ref["adoption"]) == 6


def test_nlp():
    assert nl.lemmatize("better") == "good" and nl.lemmatize("ran") == "run" and nl.stem("making") == "make"
    assert nl.stem("universal") == nl.stem("university")  # the course's stemming caveat
    tags = {x["token"]: x["tag"] for x in nl.pos_tag("I'm going to make dinner")["tags"]}
    assert tags["make"] == "VERB"
    tags = {x["token"]: x["tag"] for x in nl.pos_tag("What make is your laptop")["tags"]}
    assert tags["make"] == "NOUN"
    labels = {e["text"]: e["label"] for e in nl.entities("Ralph flew to Arizona and paid $2,500 on 2026-10-11")["entities"]}
    assert labels["Arizona"] == "STATE" and labels["Ralph"] == "PERSON" and labels["$2,500"] == "MONEY"
    assert nl.sentiment("terrible and broken")["label"] == "negative" and nl.sentiment("not good")["label"] == "negative"
    assert nl.spam_check("URGENT!!! You WON a free prize. Click here to verify your account")["verdict"] == "likely spam"
    u = nl.understand("add eggs and milk to my shopping list")
    assert u["structured"] == {"intent": "add_items", "items": ["eggs", "milk"], "list": "shopping list"}
    assert nl.understand("order a dozen yellow roses")["slots"]["quantity"] == 12
    assert nl.understand("blah")["intent"] is None
    with pytest.raises(nl.NlpError):
        nl.tokenize("  ")


def test_classifier_bot_rag():
    ref = nl.reference()
    c = nl.train_classifier(ref["example_classifier"], ["love it so fast", "broken and slow", "xyzzy"])
    assert [p["label"] for p in c["predictions"][:2]] == ["positive", "negative"] and c["predictions"][2]["warning"]
    with pytest.raises(nl.NlpError):
        nl.train_classifier([{"text": "a", "label": "x"}] * 3, [])
    assert nl.chatbot(ref["example_intents"], "what time do you open on friday")["matched"] == "hours"
    assert nl.chatbot(ref["example_intents"], "banana smoothie")["handed_over"]
    r = nl.rag(ref["example_docs"], "which planet has the most moons")
    assert r["grounded"] and "Saturn" in r["retrieved"][0]["passage"] and "Question:" in r["prompt"]
    assert not nl.rag(ref["example_docs"], "zebra migration")["grounded"]


def test_routes(client):
    ref = client.get("/api/aiml").json()
    assert ref["hierarchy"] and ref["nn"]["activations"] and ref["nlp"]["pipeline"]
    assert client.post("/api/aiml/neuron", json={"inputs": [1], "weights": [1, 2]}).status_code == 400
    assert client.post("/api/aiml/train", json={}).json()["accuracy"] == 1
    assert client.post("/api/aiml/metrics", json={"tp": 1, "fp": 0, "fn": 0, "tn": 1}).json()["accuracy"] == 1
    assert client.post("/api/aiml/nlp/rag", json={"docs": ref["nlp"]["example_docs"], "question": "refund time"}).status_code == 200
    assert client.post("/api/aiml/nlp/tokens", json={"text": ""}).status_code == 400
    assert client.post("/api/aiml/rules", json={}).status_code == 200
