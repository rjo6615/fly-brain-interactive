"""Formatting for the terrarium HUD and debug stream."""

def behavior_label(bridge, decoder):
    if bridge.mode != "walking":
        return bridge.mode.upper()
    left, right = bridge.left_drive, bridge.right_drive
    if max(abs(left), abs(right)) < 0.04:
        return "IDLE"
    if left < -0.04 and right < -0.04:
        return "BACKWARD"
    if abs(left - right) > 0.12:
        return "TURNING"
    return "WALKING"


def monitor_fields(controller, bridge, decoder, fly_pos, predator_distance):
    return {
        "behavior": behavior_label(bridge, decoder),
        "terrarium_selected": controller.selected_name,
        "terrarium_speed": controller.speed,
        "terrarium_paused": controller.paused,
        "fly_pos": [float(x) for x in fly_pos],
        "predator_distance": float(predator_distance),
        "p9": decoder.get_group_rate("forward"),
        "dna01": (decoder.get_normalized("DNa01_left") +
                  decoder.get_normalized("DNa01_right")) / 2,
        "dna02": (decoder.get_normalized("DNa02_left") +
                  decoder.get_normalized("DNa02_right")) / 2,
        "mdn": decoder.get_group_rate("backward"),
        "gf": decoder.get_group_rate("escape"),
        "adn1": decoder.get_group_rate("groom"),
        "mn9": decoder.get_group_rate("feed"),
    }
