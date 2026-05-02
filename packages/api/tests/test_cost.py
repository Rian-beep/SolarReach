from app.services.cost import compute_cost_cents


def test_sonnet_cost_basic():
    # Sonnet 4.6 = $3/M input, $15/M output.
    # 1_000_000 in + 100_000 out = $3.00 + $1.50 = $4.50 = 450 cents
    cents = compute_cost_cents("claude-sonnet-4-6", in_tokens=1_000_000, out_tokens=100_000)
    assert cents == 450


def test_opus_cost_basic():
    # Opus 4.7 = $15/M in, $75/M out.
    # 100k in + 10k out = $1.50 + $0.75 = $2.25 = 225 cents
    cents = compute_cost_cents("claude-opus-4-7", in_tokens=100_000, out_tokens=10_000)
    assert cents == 225


def test_cost_is_deterministic():
    a = compute_cost_cents("claude-haiku-4-5", in_tokens=12345, out_tokens=6789)
    b = compute_cost_cents("claude-haiku-4-5", in_tokens=12345, out_tokens=6789)
    assert a == b
