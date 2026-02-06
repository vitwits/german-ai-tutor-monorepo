"""
SSML utilities for proper pronunciation of abbreviations and special terms.
Automatically detects and wraps abbreviations in SSML tags.
"""

import re
from typing import Optional


def wrap_abbreviations_with_ssml(text: str, lang: str = 'de') -> str:
    """
    Detects abbreviations in text and wraps them with SSML tags for character-by-character reading.
    
    Examples:
        "CO2 emissions" → "CO<say-as interpret-as=\"characters\">CO</say-as>2 emissions"
        "USA and EU" → "<say-as interpret-as=\"characters\">USA</say-as> and <say-as interpret-as=\"characters\">EU</say-as>"
        "BMW X5" → "<say-as interpret-as=\"characters\">BMW</say-as> X5"
    
    Args:
        text: Input text to process
        lang: Language code ('de', 'uk', 'en') - used for context-aware detection
    
    Returns:
        Text with abbreviations wrapped in SSML tags
    """
    
    if not text or not isinstance(text, str):
        return text
    
    # Pattern for abbreviations:
    # - 2+ consecutive uppercase letters (optionally followed by numbers)
    # - NOT at the start of a sentence (to avoid capitalizing common words)
    # Examples: CO2, USA, EU, BMW, DNA, AI, ML, USA, IT
    
    # More aggressive pattern that catches most abbreviations
    # Matches: 2+ uppercase letters, optionally with numbers mixed in
    # But NOT single capital letter words
    abbreviation_pattern = r'\b([A-Z]{2,}(?:\d+[A-Z]*)*(?:[A-Z]*\d+)?)\b'
    
    def should_wrap(match_text: str) -> bool:
        """
        Determine if a matched text should be wrapped based on context.
        """
        # Skip very common words that shouldn't be wrapped
        skip_words = {
            # English
            'THE', 'AND', 'FOR', 'ARE', 'YOU', 'NOT', 'BUT', 'CAN', 'HAS', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET',
            'HIM', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WAY', 'WHO', 'BOY', 'DID', 'GOT', 'LET',
            'MAN', 'OWN', 'SAY', 'SHE', 'TOO', 'USE', 'US', 'IT', 'OR', 'IF', 'IN', 'AT', 'BY', 'DO', 'GO', 'NO', 'ON', 'SO', 'UP', 'IS', 'AS', 'BE', 'OF',
            # German
            'DER', 'DIE', 'DAS', 'UND', 'SEIN', 'HABEN', 'WERDEN', 'KÖNNEN', 'MÜSSEN', 'WOLLEN', 'SOLLEN', 'DÜRFEN',
            'MACHEN', 'GEHEN', 'KOMMEN', 'SAGEN', 'GEBEN', 'NEHMEN', 'HALTEN', 'FINDEN', 'STELLEN', 'ZEIGEN', 'BLEIBT',
            'DEN', 'EIN', 'EINE', 'EINEM', 'EINEN', 'EINER', 'EINES', 'AUS', 'ZU', 'MIT', 'VON', 'FÜR', 'VOR', 'NACH',
            'EIN', 'ZWEI', 'DREI', 'VIER', 'FÜNF', 'SECHS', 'SIEBEN', 'ACHT', 'NEUN', 'ZEHN',
            'WAS', 'WER', 'WO', 'WANN', 'WARUM', 'WIE', 'JA', 'NEIN', 'ICH', 'DU', 'ER', 'IHR',
            # Ukrainian
            'ТА', 'I', 'НА', 'В', 'ДО', 'У', 'З', 'З', 'ЛЕ', 'БИ', 'БЕЗ', 'ПРИ', 'ПІДІ', 'ЧЕЗ', 'ЧЕРЕЗ',
            'ЦЕ', 'ЦЕ', 'ТОМУ', 'ТОБТО', 'ОДНАК', 'АЛЕ', 'ЧОМУ', 'КОЛИ', 'КОЛЬ', 'ДЕ', 'КДЕ', 'КОЛИ', 'ЯК',
            'ЯКА', 'ЯКЕ', 'ЯКІ', 'ЯКИЙ', 'ТАКИЙ', 'ТАКИЙ', 'ЯКИЙ', 'ЦЕЙ', 'ЦЬОГО', 'ОТ', 'ОТЖЕ', 'ОТАК', 'ОТЖЕ',
            'ЕЙ', 'О', 'А', 'Е', 'Ю', 'Я', 'Ї',
        }
        
        # Don't wrap if it's a common word
        if match_text in skip_words:
            return False
        
        # Don't wrap if it's only 1 character
        if len(match_text) < 2:
            return False
        
        # Wrap if it looks like a real abbreviation
        # (has mostly letters and/or numbers, not too long)
        uppercase_count = sum(1 for c in match_text if c.isupper())
        digit_count = sum(1 for c in match_text if c.isdigit())
        
        # If 80% or more are uppercase letters or digits, it's likely an abbreviation
        if (uppercase_count + digit_count) / len(match_text) >= 0.8:
            return True
        
        return False
    
    def replace_abbreviation(match):
        """Replace matched abbreviation with SSML-wrapped version."""
        abbrev = match.group(1)
        
        if should_wrap(abbrev):
            return f'<say-as interpret-as="characters">{abbrev}</say-as>'
        else:
            return abbrev
    
    # Apply the replacement
    result = re.sub(abbreviation_pattern, replace_abbreviation, text)
    
    return result


def unwrap_ssml_abbreviations(text: str) -> str:
    """
    Remove SSML tags from text (useful for display/storage without markup).
    
    Args:
        text: Text potentially containing SSML tags
    
    Returns:
        Text with SSML tags removed
    """
    if not text:
        return text
    
    # Remove SSML say-as tags
    pattern = r'<say-as[^>]*>(.*?)</say-as>'
    return re.sub(pattern, r'\1', text)


# Abbreviations to READ CHARACTER-BY-CHARACTER (using SSML)
# These sound wrong when read as words, so they MUST be spelled out
CHAR_BY_CHAR_ABBREVIATIONS = {
    # Tech/IT - ініціали, які не утворюють слова
    'AI', 'ML', 'API', 'HTTP', 'HTTPS', 'SSL', 'TCP', 'IP', 'DNS', 'CPU', 'GPU', 'SSD', 'USB',
    'HTML', 'CSS', 'PHP', 'SQL', 'JSON', 'XML', 'PDF', 'URL', 'VPN', 'SSH', 'FTP', 'AWS', 'VM', 'OS',
    'NPM', 'SDK', 'IDE', 'DB', 'UI', 'UX', 'CMS', 'CDN',
    'DL', 'LLM', 'AGI', 'TLS', 'UDP', 'IPv6', 'NVMe', 'JS', 'TS', 'CI', 'CD', 'K8s', 'ORM', 'DX',
    'NFT', 'DeFi', 'DAO', 'SRE', 'IaC',

    # Science/Health - ініціали та хімічні формули
    'CO2', 'H2O', 'O2', 'DNA', 'RNA', 'HIV', 'WHO', 'FDA', 'EPA', 'NIH', 'CDC', 'BMI',
    'PCR', 'GIS', 'PhD', 'MD', 'RN', 'MRI', 'CT', 'EEG', 'EMG', 'CRISPR', 'CAPCHA',
    'mRNA', 'EMA', 'NHS', 'ECG', 'PET', 'NAD', 'NMN', 'GLP-1',

    # Organizations - ініціали (букви державних агентств тощо)
    'USA', 'EU', 'UK', 'FBI', 'CIA', 'MIT', 'IBM', 'BBC', 'CNN', 'NFL', 'NBA',
    'IMF', 'UN', 'G7', 'G20',
    'NSA', 'ESA', 'WB', 'WTO',

    # Car brands - ініціали компаній
    'BMW', 'VW', 'MB',

    # Universities/Education - ініціали тестів
    'TOEFL', 'IELTS', 'SAT', 'GRE', 'GMAT', 'DELF', 'DALF', 'DELE', 'JLPT',

    # Internet/Text speak - абревіатури, що звучать дивно
    'IDK', 'IDC', 'NGL', 'SMH', 'PMO', 'ATP', 'FAFO', 'WYLL', 'WYS', 'PSA',
    'DM', 'AMA', 'EOD', 'TMI', 'NSFW', 'SFW', 'IRL', 'AF', 'TIL', 'IIRC', 'TLDR',
    'OTP', 'DNI', 'BDE', 'ROI', 'KPI', 'OKR', 'B2B', 'B2C', 'C2C', 'CRM', 'ERP', 'IPO', 'VC', 'PE', 'M&A',

    # Gaming
    'GG', 'WP', 'EZ', 'LFG', 'OP', 'DPS',

    # Інші ініціали
    'ID', 'CV', 'CEO', 'CFO', 'CTO', 'HR', 'PR', 'QA', 'ETA', 'FAQ', 'AM', 'PM',
    'ASAP', 'AFAIK', 'FYI', 'BTW', 'IMO', 'IMHO', 'PS', 'PPS',
    'ETC', 'AKA', 'TBD', 'TBA', 'AOK', 'BRB', 'TTYL', 'MBA',
    'LMAO', 'LMFAO', 'ROFL', 'AFK', 'GTG', 'G2G', 'TTYS', 'TBH',
    'HMU', 'HBU', 'FB', 'MSG', 'ABT', 'ATM', 'B4', 'TGIF', 'HBD', 'ILY', 'LMK', 'NP', 'TY', 'YW',
}


# Mapping of abbreviations to their correct pronunciation by language
WORD_PRONUNCIATION = {
    'de': {  # German
        # Car brands
        'AUDI': 'Audi',
        'KIA': 'Kia',
        'FORD': 'Ford',
        'TOYOTA': 'Toyota',
        'TESLA': 'Tesla',
        'LEGO': 'Lego',
        'ADIDAS': 'Adidas',
        'PUMA': 'Puma',
        'MERCEDES': 'Mercedes',
        'BMW': 'Beamer',
        'PORSCHE': 'Porsche',
        'LAMBORGHINI': 'Lamborghini',
        'DUCATI': 'Ducati',
        'HARLEY': 'Harley',
        'VESPA': 'Vespa',
        
        # International organizations
        'UNESCO': 'Unesco',
        'UNICEF': 'Unizef',
        'NATO': 'Nato',
        'FIFA': 'Fifa',
        'OPEC': 'Opek',
        'ASEAN': 'Asean',
        'BRICS': 'Brix',
        'INTERPOL': 'Interpol',
        'EUROPOL': 'Europol',
        'WHO': 'Wer-Haus-O',
        'UNICEF': 'Junizeff',
        'UNIDO': 'Unido',
        'UNWTO': 'Unwto',
        'UNHCR': 'Unhcr',
        'WIPO': 'Wipo',
        
        # Health & Medicine
        'AIDS': 'Aids',
        'COVID': 'Covid',
        'SARS': 'Sars',
        'MRSA': 'Mersa',
        'EBOLA': 'Ebola',
        'RSV': 'Ar-Äss-Weh',
        'ADHD': 'A-D-H-D',
        'PTSD': 'P-T-S-D',
        'COPD': 'K-O-P-D',
        
        # Technology
        'SAAS': 'Saas',
        'PAAS': 'Paas',
        'IAAS': 'Iaas',
        'NOSQL': 'Nosql',
        'REST': 'Rest',
        'GIT': 'Git',
        'SIM': 'Sim',
        'PIN': 'Pin',
        'RAM': 'Ram',
        'ROM': 'Rom',
        'GUI': 'Gui',
        'DAPP': 'Dapp',
        'BLOCKCHAIN': 'Blockchein',
        'CRYPTO': 'Krypto',
        'BITCOIN': 'Bitcoin',
        'ETHEREUM': 'Ethereum',
        'METAVERSE': 'Metaverse',
        
        # Social Media & Platforms
        'LOL': 'Lol',
        'WOW': 'Wow',
        'OMG': 'Omg',
        'BFF': 'Bff',
        'BAE': 'Bae',
        'JK': 'Jk',
        'FOMO': 'Fomo',
        'HODL': 'Hodl',
        'NVM': 'Nvm',
        'LMAO': 'Lmao',
        'ROFL': 'Rofl',
        'YOLO': 'Yolo',
        'TIKTOK': 'TikTok',
        'INSTAGRAM': 'Instagram',
        'YOUTUBE': 'YouTube',
        'SNAPCHAT': 'Snapchat',
        'TWITCH': 'Twitch',
        'DISCORD': 'Discord',
        'SLACK': 'Slack',
        'ZOOM': 'Zoom',
        'REDDIT': 'Reddit',
        'PINTEREST': 'Pinterest',
        'WHATSAPP': 'WhatsApp',
        'TELEGRAM': 'Telegram',
        'SIGNAL': 'Signal',
        'VIBER': 'Viber',
        'MESSENGER': 'Messenger',
        
        # Food & Beverage Brands
        'MCDONALD': 'Mäkkis',
        'STARBUCKS': 'Starbocks',
        'COCA': 'Koka',
        'FANTA': 'Fanta',
        'SPRITE': 'Sprite',
        'PEPSI': 'Pepsi',
        'HEINEKEN': 'Heineken',
        'CARLSBERG': 'Carlsberg',
        
        # Fashion Brands
        'GUCCI': 'Gutschi',
        'LOUIS': 'Lui',
        'CHANEL': 'Schanel',
        'VERSACE': 'Versatsche',
        'PRADA': 'Prada',
        'ZARA': 'Zara',
        'NIKE': 'Naiki',
        'REEBOK': 'Ribok',
        'CONVERSE': 'Konwers',
        'VANS': 'Wans',
        
        # German specific
        'DAAD': 'Daad',
        'BAFÖG': 'Bafög',
        'ZDF': 'Zed-E-Eff',
        'ARD': 'Ar-Ar-De',
        'DLR': 'Dehlerre',
        'DGB': 'Degebeh',
    },
    'uk': {  # Ukrainian
        # Car brands
        'AUDI': 'Ауді',
        'KIA': 'Ків',
        'FORD': 'Форд',
        'TOYOTA': 'Тойота',
        'TESLA': 'Тесла',
        'LEGO': 'Лего',
        'ADIDAS': 'Адідас',
        'PUMA': 'Пума',
        'MERCEDES': 'Мерседес',
        'BMW': 'Бі-Ем-Ве',
        'PORSCHE': 'Поршე',
        'LAMBORGHINI': 'Ламборгіні',
        'DUCATI': 'Дукаті',
        'HARLEY': 'Харлей',
        'VESPA': 'Веспа',
        
        # International organizations
        'UNESCO': 'Юнеско',
        'UNICEF': 'Юнісеф',
        'NATO': 'Нато',
        'FIFA': 'Фіфа',
        'OPEC': 'Опек',
        'ASEAN': 'Асеан',
        'BRICS': 'Брікс',
        'INTERPOL': 'Інтерпол',
        'EUROPOL': 'Європол',
        'WHO': 'Всесвітня організація охорони здоров\'я',
        'UNIDO': 'Унідо',
        'UNWTO': 'Унвто',
        'UNHCR': 'УВКБ',
        'WIPO': 'ВОІВ',
        
        # Health & Medicine
        'AIDS': 'СНІД',
        'COVID': 'Ковід',
        'SARS': 'САРС',
        'MRSA': 'Мерса',
        'EBOLA': 'Еболе',
        'RSV': 'РСВ',
        'ADHD': 'СДВГ',
        'PTSD': 'ПТСР',
        'COPD': 'ХОЗЛ',
        
        # Technology
        'SAAS': 'СааС',
        'PAAS': 'ПааС',
        'IAAS': 'ІааС',
        'NOSQL': 'НоSQL',
        'REST': 'Рест',
        'GIT': 'Гіт',
        'SIM': 'СІМ',
        'PIN': 'ПІН',
        'RAM': 'ОЗП',
        'ROM': 'ПЗП',
        'GUI': 'ГІС',
        'DAPP': 'Дапп',
        'BLOCKCHAIN': 'Блокчейн',
        'CRYPTO': 'Крипто',
        'BITCOIN': 'Біткоїн',
        'ETHEREUM': 'Етеріум',
        'METAVERSE': 'Метавсесвіт',
        
        # Social Media & Platforms
        'LOL': 'ЛОЛ',
        'WOW': 'ВОВ',
        'OMG': 'О-М-Ж',
        'BFF': 'БФФ',
        'BAE': 'Бей',
        'JK': 'Джей-Кей',
        'FOMO': 'Фомо',
        'HODL': 'Холдл',
        'NVM': 'НВМ',
        'LMAO': 'ЛМАО',
        'ROFL': 'РОФЛ',
        'YOLO': 'Йоло',
        'TIKTOK': 'ТіКТок',
        'INSTAGRAM': 'Інстаграм',
        'YOUTUBE': 'Ютуб',
        'SNAPCHAT': 'Снапчат',
        'TWITCH': 'Твіч',
        'DISCORD': 'Дискорд',
        'SLACK': 'Слак',
        'ZOOM': 'Зум',
        'REDDIT': 'Редіт',
        'PINTEREST': 'Пінтерест',
        'WHATSAPP': 'ВатсАпп',
        'TELEGRAM': 'Телеграм',
        'SIGNAL': 'Сигнал',
        'VIBER': 'Вайбер',
        'MESSENGER': 'Месенджер',
        
        # Food & Beverage Brands
        'MCDONALD': 'Макдональдс',
        'STARBUCKS': 'Старбакс',
        'COCA': 'Кока',
        'FANTA': 'Фанта',
        'SPRITE': 'Спрайт',
        'PEPSI': 'Пепсі',
        'HEINEKEN': 'Гайнекен',
        'CARLSBERG': 'Карлсберг',
        
        # Fashion Brands
        'GUCCI': 'Гуччі',
        'LOUIS': 'Луї',
        'CHANEL': 'Шанель',
        'VERSACE': 'Версаче',
        'PRADA': 'Прада',
        'ZARA': 'Зара',
        'NIKE': 'Найк',
        'REEBOK': 'Рібок',
        'CONVERSE': 'Конверс',
        'VANS': 'Ванс',
        
        # Other
        'DAAD': 'DAAD',
        'BAFÖG': 'БаФьог',
        'ZDF': 'Цед-Е-Еф',
        'ARD': 'Ар-Ар-Де',
        'DLR': 'Деелерре',
        'DGB': 'Деgebeh',
    },
    'en': {  # English
        # Car brands
        'AUDI': 'Audi',
        'KIA': 'Kia',
        'FORD': 'Ford',
        'TOYOTA': 'Toyota',
        'TESLA': 'Tesla',
        'LEGO': 'Lego',
        'ADIDAS': 'Adidas',
        'PUMA': 'Puma',
        'MERCEDES': 'Mercedes',
        'BMW': 'BMW',
        'PORSCHE': 'Porsche',
        'LAMBORGHINI': 'Lamborghini',
        'DUCATI': 'Ducati',
        'HARLEY': 'Harley',
        'VESPA': 'Vespa',
        
        # International organizations
        'UNESCO': 'UNESCO',
        'UNICEF': 'UNICEF',
        'NATO': 'NATO',
        'FIFA': 'FIFA',
        'OPEC': 'OPEC',
        'ASEAN': 'ASEAN',
        'BRICS': 'BRICS',
        'INTERPOL': 'Interpol',
        'EUROPOL': 'Europol',
        'WHO': 'WHO',
        'UNIDO': 'UNIDO',
        'UNWTO': 'UNWTO',
        'UNHCR': 'UNHCR',
        'WIPO': 'WIPO',
        
        # Health & Medicine
        'AIDS': 'AIDS',
        'COVID': 'COVID',
        'SARS': 'SARS',
        'MRSA': 'MRSA',
        'EBOLA': 'Ebola',
        'RSV': 'RSV',
        'ADHD': 'ADHD',
        'PTSD': 'PTSD',
        'COPD': 'COPD',
        
        # Technology
        'SAAS': 'SaaS',
        'PAAS': 'PaaS',
        'IAAS': 'IaaS',
        'NOSQL': 'NoSQL',
        'REST': 'REST',
        'GIT': 'Git',
        'SIM': 'SIM',
        'PIN': 'PIN',
        'RAM': 'RAM',
        'ROM': 'ROM',
        'GUI': 'GUI',
        'DAPP': 'DApp',
        'BLOCKCHAIN': 'Blockchain',
        'CRYPTO': 'Crypto',
        'BITCOIN': 'Bitcoin',
        'ETHEREUM': 'Ethereum',
        'METAVERSE': 'Metaverse',
        
        # Social Media & Platforms
        'LOL': 'LOL',
        'WOW': 'WOW',
        'OMG': 'OMG',
        'BFF': 'BFF',
        'BAE': 'Bae',
        'JK': 'JK',
        'FOMO': 'FOMO',
        'HODL': 'HODL',
        'NVM': 'NVM',
        'LMAO': 'LMAO',
        'ROFL': 'ROFL',
        'YOLO': 'YOLO',
        'TIKTOK': 'TikTok',
        'INSTAGRAM': 'Instagram',
        'YOUTUBE': 'YouTube',
        'SNAPCHAT': 'Snapchat',
        'TWITCH': 'Twitch',
        'DISCORD': 'Discord',
        'SLACK': 'Slack',
        'ZOOM': 'Zoom',
        'REDDIT': 'Reddit',
        'PINTEREST': 'Pinterest',
        'WHATSAPP': 'WhatsApp',
        'TELEGRAM': 'Telegram',
        'SIGNAL': 'Signal',
        'VIBER': 'Viber',
        'MESSENGER': 'Messenger',
        
        # Food & Beverage Brands
        'MCDONALD': 'McDonald\'s',
        'STARBUCKS': 'Starbucks',
        'COCA': 'Coca',
        'FANTA': 'Fanta',
        'SPRITE': 'Sprite',
        'PEPSI': 'Pepsi',
        'HEINEKEN': 'Heineken',
        'CARLSBERG': 'Carlsberg',
        
        # Fashion Brands
        'GUCCI': 'Gucci',
        'LOUIS': 'Louis Vuitton',
        'CHANEL': 'Chanel',
        'VERSACE': 'Versace',
        'PRADA': 'Prada',
        'ZARA': 'Zara',
        'NIKE': 'Nike',
        'REEBOK': 'Reebok',
        'CONVERSE': 'Converse',
        'VANS': 'Vans',
        
        # Other
        'DAAD': 'DAAD',
        'BAFÖG': 'BAföG',
        'ZDF': 'ZDF',
        'ARD': 'ARD',
        'DLR': 'DLR',
        'DGB': 'DGB',
    }
}


# Abbreviations to READ AS WORDS (not character-by-character)
# These should be pronounced as complete words/proper nouns
READ_AS_WORDS = {
    # Car brands
    'AUDI', 'KIA', 'FORD', 'TOYOTA', 'TESLA', 'LEGO', 'ADIDAS', 'PUMA',
    'MERCEDES', 'PORSCHE', 'LAMBORGHINI', 'DUCATI', 'HARLEY', 'VESPA',
    
    # International organizations
    'UNESCO', 'UNICEF', 'NATO', 'FIFA', 'OPEC', 'ASEAN', 'BRICS', 'INTERPOL', 'EUROPOL',
    'WHO', 'UNIDO', 'UNWTO', 'UNHCR', 'WIPO',
    
    # Health & Medicine
    'AIDS', 'COVID', 'SARS', 'MRSA', 'EBOLA', 'RSV', 'ADHD', 'PTSD', 'COPD',
    
    # Technology
    'SAAS', 'PAAS', 'IAAS', 'NOSQL', 'REST', 'GIT', 'SIM', 'PIN',
    'RAM', 'ROM', 'GUI', 'DAPP', 'BLOCKCHAIN', 'CRYPTO', 'BITCOIN', 'ETHEREUM', 'METAVERSE',
    
    # Social Media & Platforms
    'LOL', 'WOW', 'OMG', 'BFF', 'BAE', 'JK', 'FOMO', 'HODL', 'NVM',
    'LMAO', 'ROFL', 'YOLO',
    'TIKTOK', 'INSTAGRAM', 'YOUTUBE', 'SNAPCHAT', 'TWITCH', 'DISCORD', 'SLACK', 'ZOOM',
    'REDDIT', 'PINTEREST', 'WHATSAPP', 'TELEGRAM', 'SIGNAL', 'VIBER', 'MESSENGER',
    
    # Food & Beverage Brands
    'MCDONALD', 'STARBUCKS', 'COCA', 'FANTA', 'SPRITE', 'PEPSI', 'HEINEKEN', 'CARLSBERG',
    
    # Fashion Brands
    'GUCCI', 'LOUIS', 'CHANEL', 'VERSACE', 'PRADA', 'ZARA', 'NIKE', 'REEBOK', 'CONVERSE', 'VANS',
    
    # Other
    'DAAD', 'BAFÖG', 'ZDF', 'ARD', 'DLR', 'DGB', 'NASA',
}


def force_wrap_known_abbreviations(text: str) -> str:
    """
    Wrap abbreviations that MUST be pronounced character-by-character.
    Skips abbreviations that should be read as words (READ_AS_WORDS set).
    
    Args:
        text: Input text
    
    Returns:
        Text with CHAR_BY_CHAR abbreviations wrapped in SSML tags
    """
    if not text:
        return text
    
    result = text
    
    # Sort by length (longest first) to avoid partial replacements
    for abbrev in sorted(CHAR_BY_CHAR_ABBREVIATIONS, key=len, reverse=True):
        # Use word boundaries to match whole words only
        pattern = r'\b' + re.escape(abbrev) + r'\b'
        replacement = f'<say-as interpret-as="characters">{abbrev}</say-as>'
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def prepare_text_for_tts(text: str, lang: str = 'de', use_smart_wrapping: bool = True) -> str:
    """
    Main function to prepare text for TTS with proper SSML handling.
    
    Strategy:
    1. Wrap word-like abbreviations with SSML tag marking them as words (READ_AS_WORDS)
       Uses language-specific pronunciation from WORD_PRONUNCIATION dictionary
    2. Force wrap character-by-character abbreviations (CHAR_BY_CHAR_ABBREVIATIONS)
    3. Optionally apply smart regex detection for other abbreviations
    
    Args:
        text: Raw text input
        lang: Language code ('de', 'uk', 'en')
        use_smart_wrapping: Whether to use regex-based smart detection
    
    Returns:
        Text ready for TTS synthesis with SSML tags
    """
    if not text:
        return text
    
    result = text
    
    # Step 1: Wrap word-like abbreviations with special tag to mark as words
    # Use language-specific pronunciation from WORD_PRONUNCIATION
    pron_dict = WORD_PRONUNCIATION.get(lang, WORD_PRONUNCIATION.get('de', {}))
    
    for abbrev in sorted(READ_AS_WORDS, key=len, reverse=True):
        # Get the correct pronunciation for this language
        pronunciation = pron_dict.get(abbrev, abbrev.capitalize())
        
        # Use word boundary to match whole word
        pattern = r'\b' + re.escape(abbrev) + r'\b'
        # Wrap in sub tag - the alias tells TTS what word to speak
        replacement = f'<sub alias="{pronunciation}">{abbrev}</sub>'
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    # Step 2: Force wrap character-by-character abbreviations
    result = force_wrap_known_abbreviations(result)
    
    # Step 3: Smart wrapping if enabled
    if use_smart_wrapping:
        # Only apply if not already wrapped to avoid double-wrapping
        if '<say-as' not in result and '<sub' not in result:
            result = wrap_abbreviations_with_ssml(result, lang)
    
    return result
