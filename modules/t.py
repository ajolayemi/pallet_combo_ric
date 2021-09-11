a = {'Euro': {'PED 73 (B2C-PL) del 17/12/2020': 56,
              'PED 74 (B2C-PL) del 17/12/2020': 56, 'PED 75 (B2C-PL) del 17/12/2020': 56,
              'PED 76 (B2C-PL) del 17/12/2020': 56, 'PED 77 (B2C-PL) del 17/12/2020': 56,
              'PED 78 (B2C-PL) del 17/12/2020': 56, 'PED 79 (B2C-PL) del 17/12/2020': 56,
              'PED 80 (B2C-PL) del 17/12/2020': 56, 'PED 81 (B2C-PL) del 17/12/2020': 56,
              'PED 82 (B2C-PL) del 17/12/2020': 56, 'PED 83 (B2C-PL) del 17/12/2020': 56,
              'PED 84 (B2C-PL) del 17/12/2020': 56, 'PED 85 (B2C-PL) del 17/12/2020': 48,
              'PED 86 (B2C-PL) del 17/12/2020': 48, 'PED 87 (B2C-PL) del 17/12/2020': 48,
              'PED 88 (B2C-PL) del 17/12/2020': 56, 'PED 89 (B2C-PL) del 17/12/2020': 48,
              'PED 90 (B2C-PL) del 17/12/2020': 43}}


if __name__ == '__main__':
    s = 0
    for i in a['Euro'].values():
        s += i

    print(s)
