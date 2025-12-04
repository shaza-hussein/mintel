import math

PRICING_CONFIG = {
    'services': {
        'voice': {
            'anchor_price': 200,
            'anchor_rate': 13.3,
            'floor_rate': 6.0,
            'max_price': 10000,
            'unit_name': 'Minutes',
            'daily_points': [
                [100, 20.0], [150, 16.67], [175, 15.91], [200, 12.5], [220, 12.22],
                [230, 12.11], [300, 10.71], [450, 8.82], [540, 8.44], [750, 7.14], [800, 6.67]
            ],
            'weekly_points': [
                [300, 18.75], [420, 14.0], [525, 12.21], [650, 10.83], [750, 10.0],
                [840, 9.13], [935, 8.90], [1650, 7.5], [3520, 7.04], [5000, 6.25], [5390, 6.19]
            ],
            'decay_k': None
        },
        'data': {
            'anchor_price': 650,
            'anchor_rate': 0.42,
            'floor_rate': 0.2,
            'max_price': 10000,
            'unit_name': 'MB',
            'daily_points': [
                [100, 2.0], [190, 1.583], [220, 1.294], [290, 1.16], [650, 0.42]
            ],
            'decay_k': None
        },
        'sms': {
            'anchor_price': 50,
            'anchor_rate': 1.3,
            'floor_rate': 0.2,
            'max_price': 500,
            'unit_name': 'SMS',
            'decay_k': None
        }
    },
    'validity_premiums': {
        1: 0,
        2: 25,
        3: 50,
        7: 120,
        30: 235
    },
    'mixed_bundle_discounts': {
        1: 0,
        2: 10,
        3: 20
    },
    'btl_discounts': {
        'atl': 0,
        'diy_mode': -5,
        'promotion_mode':0,
        'btl_normal': 20,
        'btl_moderate': 30,
        'btl_aggressive': 40
    },
    'rounding_rules': {
        'data_round_to': 5
    },
    'minimums': {
        'price': {'voice': 100, 'data': 100},
        'volume': {'voice': 5, 'data': 50},
        'multi_service_volume': {'voice': 5, 'data': 50, 'sms': 0}
    },
    'promotion_mode_param': {
        'voice': {'starting_price': 150, 'ending_price': 2000,'discount':35,'validity':-1},
        'data': {'starting_price': 0, 'ending_price': 0,'discount':0,'validity':-1},
        'sms': {'starting_price': 0, 'ending_price': 0,'discount':0,'validity':-1},
    }
}

def recalculate_decay(anchor_price, anchor_rate, floor_rate, max_price):
    if anchor_rate <= floor_rate or max_price <= anchor_price:
        return math.nan
    rate_at_max = floor_rate + 0.01
    numerator = math.log((rate_at_max - floor_rate) / (anchor_rate - floor_rate))
    denominator = max_price - anchor_price
    return -numerator / denominator

def interpolate(x, points):
    if x < points[0][0]:
        x1, y1 = points[0]
        x2, y2 = points[1]
        slope = (y2 - y1) / (x2 - x1) if (x2 - x1) != 0 else 0
        return y1 + (x - x1) * slope
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        if x1 <= x < x2:
            return y1 + (x - x1) * (y2 - y1) / (x2 - x1)
    return points[-1][1]

def get_vpm(validity_days, premiums_config):
    points = sorted([[int(k), v] for k, v in premiums_config.items()])
    premium = interpolate(validity_days, points)
    return 1 + premium / 100.0

def calculate_volume_from_price(price, service, validity_days, num_services, offer_type, config,mbdf_per):
    s_config = config['services'][service]
 
    mbdf = 1 - (mbdf_per * config['mixed_bundle_discounts'].get(2, 0) / 100.0)
    starting_price = config['promotion_mode_param'][service].get('starting_price',0)
    ending_price = config['promotion_mode_param'][service].get('ending_price',0)
    promo_val = config['promotion_mode_param'][service].get('validity',0)
    if num_services == 1  and offer_type == 'promotion_mode' and price >= starting_price  and price <= ending_price and (promo_val==-1 or promo_val == validity_days ): 
        tdf = 1 - (config['promotion_mode_param'][service].get('discount', 0) / 100.0) 
    else:
        tdf = 1 - (config['btl_discounts'].get(offer_type, 0) / 100.0)

    
    if s_config.get('decay_k') is None:
        s_config['decay_k'] = recalculate_decay(
            s_config['anchor_price'], s_config['anchor_rate'],
            s_config['floor_rate'], s_config['max_price'])

    final_er = 0
    if service == 'voice':
        points = s_config['weekly_points'] if validity_days == 7 else s_config['daily_points']
        last_price_point = points[-1][0]
        er_price = 0
        if price > last_price_point:
            k = s_config['decay_k']
            er_price = s_config['floor_rate'] + (points[-1][1] - s_config['floor_rate']) * math.exp(-k * (price - last_price_point))
        else:
            er_price = interpolate(price, points)
        final_er = er_price if validity_days == 7 else er_price * get_vpm(validity_days, config['validity_premiums'])
    elif service == 'data':
        er_price_base = 0
        if price <= s_config['anchor_price']:
            er_price_base = interpolate(price, s_config['daily_points'])
        else:
            k = s_config['decay_k']
            er_price_base = s_config['floor_rate'] + (s_config['anchor_rate'] - s_config['floor_rate']) * math.exp(-k * (price - s_config['anchor_price']))
        final_er = er_price_base * get_vpm(validity_days, config['validity_premiums'])
    else: # sms
        k = s_config['decay_k']
        er_price = s_config['floor_rate'] + (s_config['anchor_rate'] - s_config['floor_rate']) * math.exp(-k * (price - s_config['anchor_price']))
        final_er = er_price * get_vpm(validity_days, config['validity_premiums'])

    ultimate_er = final_er * mbdf * tdf

    return price / ultimate_er if ultimate_er > 0 else 0

def calculate_bundle(service_allocations, validity_days, offer_type, config):
    active_services = {s: p for s, p in service_allocations.items() if p > 0}
    num_services = len(active_services)
    
    sorted_keys = sorted(active_services, key=active_services.get)
    smallest_ser = {k: (1 if i < num_services-1 else 0) for i, k in enumerate(sorted_keys)}
    active_services = {s: p for s, p in service_allocations.items() if p > 0}
    num_services = len(active_services)
    final_offer = {'units': {}}

    for service, price in active_services.items():
        unrounded_units = calculate_volume_from_price(price, service, validity_days, num_services, offer_type, config,smallest_ser[service])
        s_config = config['services'][service]
        
        if service == 'data':
            rounded_units = math.ceil(unrounded_units / config['rounding_rules']['data_round_to']) * config['rounding_rules']['data_round_to']
        else:
            rounded_units = round(unrounded_units)
        
        final_offer['units'][service] = f"{rounded_units} {s_config['unit_name']}"
    
    return final_offer

def find_price_for_volume(service, target_volume, validity_days, offer_type, num_services, config,mbdf_per):
    s_config = config['services'][service]
    low_price, high_price = 0.01, s_config['max_price']

    def get_rounded_volume(price_guess):
        unrounded_units = calculate_volume_from_price(price_guess, service, validity_days, num_services, offer_type, config,mbdf_per)
        if service == 'data':
            return math.ceil(unrounded_units / config['rounding_rules']['data_round_to']) * config['rounding_rules']['data_round_to']
        else:
            return round(unrounded_units)

    for _ in range(100):
        guess_price = (low_price + high_price) / 2
        rounded_units = get_rounded_volume(guess_price)
        if rounded_units < target_volume:
            low_price = guess_price
        else:
            high_price = guess_price
        if (high_price - low_price) < 0.001:
            break
            
    return high_price

def calculate_price_from_volume(target_volumes, validity_days, offer_type, config):
    active_services = {s: v for s, v in target_volumes.items() if v > 0}
    num_services = len(active_services)
    service_prices = {
    service: active_services[service] * PRICING_CONFIG['services'][service]['anchor_rate']
                    for service in active_services  }

    sorted_keys = sorted(service_prices, key=service_prices.get)
    smallest_ser = {k: (1 if i < num_services-1 else 0) for i, k in enumerate(sorted_keys)}


    if num_services > 1:
        for service, volume in active_services.items():
            min_vol = config['minimums']['multi_service_volume'].get(service)
            if min_vol and volume < min_vol:
                return {'error': f"Error: Minimum for {service} in a multi-buy is {min_vol}."}

    individual_prices = {}
    sub_total_price = 0
    for service, volume in active_services.items():
        price = find_price_for_volume(service, volume, validity_days, offer_type, num_services, config,smallest_ser[service])
        
        min_price = config['minimums']['price'].get(service)
        final_price = price if min_price is None or price >= min_price else min_price
        
        individual_prices[service] = final_price
        sub_total_price += final_price
    
    final_total_price = round(sub_total_price)
    
    return {
        'calculated_price': final_total_price,
        'individual_prices': individual_prices
    }