# apps/core/utils.py
# ─────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# can_deliver — validates delivery zone (state border check)
# ─────────────────────────────────────────────────────────────

# Nigerian state border map
# Each state lists its directly bordering states
STATE_BORDERS = {
    'Abia': ['Imo', 'Anambra', 'Enugu', 'Cross River', 'Akwa Ibom'],
    'Adamawa': ['Taraba', 'Gombe', 'Borno'],
    'Akwa Ibom': ['Cross River', 'Rivers', 'Abia'],
    'Anambra': ['Imo', 'Abia', 'Enugu', 'Kogi', 'Delta'],
    'Bauchi': ['Gombe', 'Yobe', 'Borno', 'Taraba', 'Plateau', 'Kaduna', 'Jigawa', 'Kano'],
    'Bayelsa': ['Rivers', 'Delta'],
    'Benue': ['Kogi', 'Enugu', 'Cross River', 'Taraba', 'Nasarawa', 'Plateau'],
    'Borno': ['Adamawa', 'Gombe', 'Bauchi', 'Yobe'],
    'Cross River': ['Benue', 'Ebonyi', 'Enugu', 'Abia', 'Akwa Ibom'],
    'Delta': ['Bayelsa', 'Rivers', 'Imo', 'Anambra', 'Edo', 'Ondo'],
    'Ebonyi': ['Benue', 'Cross River', 'Enugu', 'Imo', 'Abia'],
    'Edo': ['Delta', 'Anambra', 'Kogi', 'Ondo', 'Ekiti'],
    'Ekiti': ['Ondo', 'Osun', 'Kwara', 'Kogi', 'Edo'],
    'Enugu': ['Kogi', 'Benue', 'Cross River', 'Abia', 'Imo', 'Anambra', 'Ebonyi'],
    'FCT': ['Niger', 'Kaduna', 'Nasarawa', 'Kogi'],
    'Gombe': ['Bauchi', 'Taraba', 'Adamawa', 'Borno', 'Yobe'],
    'Imo': ['Abia', 'Anambra', 'Rivers', 'Delta', 'Ebonyi'],
    'Jigawa': ['Kano', 'Bauchi', 'Yobe', 'Kaduna'],
    'Kaduna': ['FCT', 'Niger', 'Kano', 'Jigawa', 'Bauchi', 'Plateau', 'Nasarawa', 'Zamfara', 'Kebbi'],
    'Kano': ['Kaduna', 'Jigawa', 'Katsina', 'Bauchi'],
    'Katsina': ['Kano', 'Zamfara', 'Jigawa'],
    'Kebbi': ['Niger', 'Kaduna', 'Zamfara', 'Sokoto'],
    'Kogi': ['FCT', 'Benue', 'Enugu', 'Anambra', 'Edo', 'Ondo', 'Ekiti', 'Kwara', 'Niger', 'Nasarawa'],
    'Kwara': ['Niger', 'FCT', 'Kogi', 'Ekiti', 'Osun', 'Oyo', 'Ogun'],
    'Lagos': ['Ogun'],
    'Nasarawa': ['FCT', 'Niger', 'Kaduna', 'Plateau', 'Benue', 'Kogi', 'Taraba'],
    'Niger': ['FCT', 'Kaduna', 'Kebbi', 'Kogi', 'Kwara', 'Zamfara'],
    'Ogun': ['Lagos', 'Oyo', 'Osun', 'Ondo'],
    'Ondo': ['Ogun', 'Osun', 'Ekiti', 'Kogi', 'Edo', 'Delta'],
    'Osun': ['Ogun', 'Oyo', 'Kwara', 'Ekiti', 'Ondo'],
    'Oyo': ['Ogun', 'Kwara', 'Osun', 'Ogut'],
    'Plateau': ['Bauchi', 'Kaduna', 'Nasarawa', 'Benue', 'Taraba'],
    'Rivers': ['Bayelsa', 'Delta', 'Imo', 'Akwa Ibom', 'Abia'],
    'Sokoto': ['Kebbi', 'Zamfara'],
    'Taraba': ['Adamawa', 'Gombe', 'Benue', 'Nasarawa', 'Plateau'],
    'Yobe': ['Borno', 'Gombe', 'Bauchi', 'Jigawa'],
    'Zamfara': ['Kebbi', 'Niger', 'Kaduna', 'Katsina', 'Sokoto'],
}


def can_deliver(seller_state, buyer_state):
    """
    Checks if seller can deliver to buyer's state.
    Seller can deliver to:
    - Their own state
    - States that directly border their state

    Interstate delivery (far states) → not covered
    Buyer must contact seller directly via WhatsApp.
    """
    if not seller_state or not buyer_state:
        return True  # Can't validate — allow through

    if seller_state == buyer_state:
        return True

    # Get bordering states
    bordering = STATE_BORDERS.get(seller_state, [])
    return buyer_state in bordering


def get_nigerian_states():
    """Returns list of all Nigerian states"""
    return sorted(STATE_BORDERS.keys())