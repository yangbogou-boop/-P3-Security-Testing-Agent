"""Conservative inspection of simulation audit prefixes; never replays actions."""


def inspect_model_prefix(events):
    prepared = set()
    sent = set()
    for event in events:
        if event.get('provenance') != 'NO_NETWORK_SIMULATION':
            continue
        action = event.get('action_id')
        if event.get('kind') == 'prepared' and isinstance(action, str):
            prepared.add(action)
        if (action in prepared and event.get('kind') == 'model_io'
                and event.get('dispatch_started') is True):
            sent.add(action)
    # A preparation / zero-byte record does not prove that the later first write
    # did not happen. Missing post-send audit must never be interpreted as zero.
    return dict(provenance='NO_NETWORK_SIMULATION', replay_allowed=False,
                model_confirmed_sent=len(sent), model_send_unknown=len(prepared - sent),
                actual_http_execution='NOT_ESTABLISHED')
