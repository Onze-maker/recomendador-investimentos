def obter_distribuicao(perfil, horizonte):
    if horizonte <= 1:
        distribuicoes = {
            "Conservador": {"Ações": 0.00, "FIIs": 0.00, "Renda fixa": 1.00},
            "Moderado":    {"Ações": 0.05, "FIIs": 0.05, "Renda fixa": 0.90},
            "Arrojado":    {"Ações": 0.10, "FIIs": 0.05, "Renda fixa": 0.85},
        }
        return distribuicoes[perfil]

    if horizonte <= 2:
        distribuicoes = {
            "Conservador": {"Ações": 0.00, "FIIs": 0.00, "Renda fixa": 1.00},
            "Moderado":    {"Ações": 0.10, "FIIs": 0.05, "Renda fixa": 0.85},
            "Arrojado":    {"Ações": 0.15, "FIIs": 0.10, "Renda fixa": 0.75},
        }
        return distribuicoes[perfil]

    return PERFIS[perfil]
