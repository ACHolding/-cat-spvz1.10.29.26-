#!/usr/bin/env python3
"""Cat's PvZ 0.1 — standalone PvZ-inspired lane-defense game.
Requires pygame-ce or pygame: python3 -m pip install pygame-ce
Run: python3 pvzcatsan0.1.py
Original procedural art; no proprietary assets included.
"""
import pygame, random, math, sys
from dataclasses import dataclass

pygame.init()
W, H = 1100, 720
screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
pygame.display.set_caption("Cat's PvZ 0.1")
clock = pygame.time.Clock()
font = pygame.font.SysFont('arial', 23, bold=True)
small = pygame.font.SysFont('arial', 17, bold=True)
big = pygame.font.SysFont('arial', 52, bold=True)

ROWS, COLS = 5, 9
X0, Y0 = 110, 175
CW, CH = 94, 94

CARDS = [('Shooter', 100, 5.5), ('Sunflower', 50, 6), ('Wall', 50, 13),
         ('Double', 175, 9), ('Frost', 175, 9), ('Bomb', 150, 15)]
CARD_RECTS = [pygame.Rect(14 + i * 180, 88, 170, 55) for i in range(len(CARDS))]
COLORS = {'Shooter': (70,170,65), 'Sunflower': (245,190,40), 'Wall': (166,113,65),
          'Double': (30,130,65), 'Frost': (80,190,220), 'Bomb': (200,65,65)}

BOMB_FUSE = 1.1
SUN_VALUE = 25
SUNFLOWER_PERIOD = 7.0
KILL_REWARD = 5
WIN_KILLS = 100

@dataclass
class Plant:
    kind: str; row: int; col: int; hp: float; timer: float = 0; age: float = 0

@dataclass
class Zombie:
    row: int; x: float; hp: float; speed: float; attack: float = 0
    slow: float = 0; armor: bool = False

@dataclass
class Pea:
    row: int; x: float; damage: float = 20; frost: bool = False

@dataclass
class Sun:
    x: float; y: float; value: int = SUN_VALUE; life: float = 9; target: float = 0

def reset():
    global plants, zombies, peas, suns, mowers, mower_active, money, wave
    global spawn_timer, sky_timer, selected, cd, game_over, won, kills, paused, hover
    plants = {}; zombies = []; peas = []; suns = []
    mowers = [True] * ROWS; mower_active = []
    money = 200; wave = 1; spawn_timer = 5; sky_timer = 4
    selected = 0; cd = [0.0] * len(CARDS)
    game_over = False; won = False; kills = 0; paused = False
    hover = None

reset()

def text(s, x, y, color=(255,255,255), f=font):
    screen.blit(f.render(str(s), True, color), (x, y))

def circle(color, pos, r):
    pygame.draw.circle(screen, color, (int(pos[0]), int(pos[1])), int(r))

def plant_center(p):
    return X0 + (p.col + .5) * CW, Y0 + (p.row + .5) * CH

def cell_at(mx, my):
    if X0 <= mx < X0 + COLS * CW and Y0 <= my < Y0 + ROWS * CH:
        return (my - Y0) // CH, (mx - X0) // CW
    return None

def draw_plant(p):
    x, y = plant_center(p); k = p.kind
    pygame.draw.ellipse(screen, (32,100,35), (x-26, y+25, 52, 15))
    pygame.draw.line(screen, (40,125,40), (x, y+24), (x, y-8), 7)
    if k == 'Sunflower':
        for i in range(10):
            a = i * math.tau / 10
            circle((255,202,45), (x + math.cos(a)*22, y - 10 + math.sin(a)*22), 12)
        circle((125,75,32), (x, y-10), 17)
        circle((20,20,20), (x-6, y-12), 3); circle((20,20,20), (x+6, y-12), 3)
    elif k == 'Wall':
        pygame.draw.rect(screen, (156,105,62), (x-26, y-35, 52, 65), border_radius=17)
        circle((40,25,20), (x-9, y-8), 4); circle((40,25,20), (x+9, y-8), 4)
    elif k == 'Bomb':
        pulse = 1 + .08 * math.sin(p.age * 22)
        circle((205,40,45), (x, y-7), 25 * pulse)
        circle((20,20,20), (x-9, y-12), 4); circle((20,20,20), (x+9, y-12), 4)
        pygame.draw.line(screen, (50,45,30), (x+8, y-28), (x+20, y-43), 4)
    else:
        color = COLORS[k]
        circle(color, (x-6, y-10), 24)
        pygame.draw.ellipse(screen, color, (x+7, y-24, 31, 23))
        circle((20,35,20), (x-12, y-15), 4)
        if k == 'Double': circle((22,80,40), (x+32, y-12), 6)
        if k == 'Frost': circle((220,250,255), (x+32, y-12), 6)
    ratio = max(0, min(1, p.hp / (450 if k == 'Wall' else 95)))
    pygame.draw.rect(screen, (40,50,40), (x-29, y+35, 58, 5))
    pygame.draw.rect(screen, (95,225,80), (x-29, y+35, 58 * ratio, 5))

def draw_zombie(z):
    y = Y0 + (z.row + .5) * CH; x = z.x
    pygame.draw.line(screen, (60,70,75), (x-9, y+12), (x-13, y+37), 7)
    pygame.draw.line(screen, (60,70,75), (x+9, y+12), (x+15, y+37), 7)
    pygame.draw.rect(screen, (90,75,95), (x-17, y-18, 34, 42), border_radius=6)
    circle((140,180,125), (x, y-33), 22)
    circle((255,255,235), (x-8, y-38), 7); circle((255,255,235), (x+9, y-38), 7)
    circle((25,25,25), (x-6, y-38), 3); circle((25,25,25), (x+11, y-38), 3)
    pygame.draw.line(screen, (65,55,55), (x-8, y-21), (x+10, y-21), 3)
    if z.armor:
        pygame.draw.polygon(screen, (160,165,175),
                            [(x-23, y-48), (x+23, y-48), (x+15, y-69), (x-15, y-69)])
    if z.slow > 0:
        pygame.draw.circle(screen, (105,220,255), (int(x), int(y-32)), 26, 2)
    pygame.draw.rect(screen, (45,40,40), (x-23, y-73, 46, 5))
    pygame.draw.rect(screen, (230,65,65),
                     (x-23, y-73, max(0, 46 * min(1, z.hp / (180 if z.armor else 100))), 5))

def spawn():
    r = random.randrange(ROWS)
    armored = random.random() < min(.5, .08 + wave * .035)
    zombies.append(Zombie(r, W + 20, 180 if armored else 100,
                          random.uniform(12, 21) + wave * 1.6, armor=armored))

def update(dt):
    global spawn_timer, sky_timer, wave, money, game_over, won, kills
    if game_over or won or paused:
        return

    for i in range(len(cd)):
        cd[i] = max(0, cd[i] - dt)

    sky_timer -= dt
    if sky_timer <= 0:
        suns.append(Sun(random.randint(X0+20, X0+COLS*CW-20), -15, SUN_VALUE, 12,
                        random.randint(Y0+20, Y0+ROWS*CH-25)))
        sky_timer = random.uniform(5, 8)

    if kills < WIN_KILLS:
        spawn_timer -= dt
        if spawn_timer <= 0:
            spawn()
            spawn_timer = max(.85, 5 - wave * .33) * random.uniform(.75, 1.25)
            if wave >= 4 and random.random() < .22:
                spawn()

    wave = 1 + kills // 12
    if kills >= WIN_KILLS and not zombies:
        won = True
        return

    for p in list(plants.values()):
        p.age += dt; p.timer -= dt
        x, y = plant_center(p)

        if p.kind == 'Sunflower' and p.timer <= 0:
            suns.append(Sun(x, y-30, SUN_VALUE, 10, y-30))
            p.timer = SUNFLOWER_PERIOD

        elif p.kind == 'Bomb':
            if p.timer <= 0:
                for z in zombies:
                    if abs(z.row - p.row) <= 1 and abs(z.x - x) < 145:
                        z.hp -= 250
                plants.pop((p.row, p.col), None)
                continue

        elif p.timer <= 0 and any(z.row == p.row and z.x > x for z in zombies):
            if p.kind == 'Frost':
                peas.append(Pea(p.row, x+27, 15, True)); p.timer = 1.5
            elif p.kind == 'Double':
                peas.append(Pea(p.row, x+27, 20)); peas.append(Pea(p.row, x+8, 20))
                p.timer = 1.2
            else:
                peas.append(Pea(p.row, x+27, 20)); p.timer = 1.35

    for b in peas[:]:
        b.x += 330 * dt
        hit = next((z for z in zombies if z.row == b.row and abs(z.x - b.x) < 19), None)
        if hit:
            hit.hp -= b.damage
            if b.frost:
                hit.slow = max(hit.slow, 3.0)
            peas.remove(b)
        elif b.x > W + 30:
            peas.remove(b)

    for z in zombies[:]:
        z.slow = max(0, z.slow - dt)
        target = next((p for p in plants.values()
                       if p.row == z.row and abs(plant_center(p)[0] - z.x) < 36), None)
        if target:
            target.hp -= 32 * dt
            if target.hp <= 0:
                plants.pop((target.row, target.col), None)
        else:
            z.x -= z.speed * dt * (.48 if z.slow > 0 else 1)

        if z.hp <= 0:
            zombies.remove(z); kills += 1; money += KILL_REWARD
            continue

        if z.x < X0 - 36:
            if mowers[z.row]:
                mowers[z.row] = False
                mower_active.append([z.row, X0 - 55])
            elif not any(r == z.row for r, _ in mower_active):
                game_over = True

    for m in mower_active[:]:
        m[1] += 510 * dt
        for z in zombies[:]:
            if z.row == m[0] and abs(z.x - m[1]) < 35:
                zombies.remove(z); kills += 1; money += KILL_REWARD
        if m[1] > W + 60:
            mower_active.remove(m)

    for s in suns[:]:
        s.life -= dt
        if s.y < s.target:
            s.y = min(s.target, s.y + 85 * dt)
        if s.life <= 0:
            suns.remove(s)

def draw():
    screen.fill((13,30,47))
    pygame.draw.rect(screen, (30,70,52), (0, 150, W, H-150))

    for r in range(ROWS):
        for c in range(COLS):
            pygame.draw.rect(screen, (76,151,73) if (r+c) % 2 else (91,168,81),
                             (X0+c*CW, Y0+r*CH, CW, CH))
            pygame.draw.rect(screen, (45,116,58), (X0+c*CW, Y0+r*CH, CW, CH), 1)

    if hover and not (game_over or won or paused):
        hr, hc = hover
        if (hr, hc) not in plants:
            pygame.draw.rect(screen, (255,255,180), (X0+hc*CW, Y0+hr*CH, CW, CH), 2)

    pygame.draw.rect(screen, (30,45,70), (0, 0, W, 150))
    text("CAT'S PVZ  •  v0.1", 20, 12, (255,226,135))
    text(f'SUN {money}    WAVE {wave}    DEFEATED {kills}/{WIN_KILLS}', 20, 48)

    for i, (name, cost, cool) in enumerate(CARDS):
        x, y = CARD_RECTS[i].topleft
        active = (i == selected)
        afford = money >= cost and cd[i] <= 0
        pygame.draw.rect(screen, (75,110,160) if active else (42,61,83),
                         CARD_RECTS[i], border_radius=9)
        pygame.draw.rect(screen, (255,230,115) if active else (100,130,155),
                         CARD_RECTS[i], 3, border_radius=9)
        circle(COLORS[name], (x+21, y+27), 13)
        text(name, x+42, y+6, (255,255,255) if afford else (165,175,185), small)
        text(f'{cost} sun', x+42, y+29, (255,224,112) if afford else (150,120,80), small)
        if cd[i] > 0:
            frac = min(1, cd[i] / cool)
            ov = pygame.Surface((170, int(55 * frac)), pygame.SRCALPHA)
            ov.fill((15,20,30,170))
            screen.blit(ov, (x, y + 55 - ov.get_height()))

    for r in range(ROWS):
        if mowers[r]:
            pygame.draw.rect(screen, (210,75,55), (X0-65, Y0+r*CH+30, 40, 28), border_radius=5)
    for r, x in mower_active:
        pygame.draw.rect(screen, (230,95,45), (x-20, Y0+r*CH+30, 40, 28), border_radius=5)

    for p in plants.values():
        draw_plant(p)
    for z in zombies:
        draw_zombie(z)
    for b in peas:
        circle((115,225,255) if b.frost else (115,240,75),
               (b.x, Y0+(b.row+.5)*CH-13), 8)
    for s in suns:
        circle((255,195,35), (s.x, s.y), 23)
        circle((255,241,130), (s.x, s.y), 16)
        text('+25', s.x-17, s.y-11, (140,80,15), small)

    text('Click cards or press 1–6 • Click lawn to plant • Click suns • P pause • R restart',
         22, 668, (240,240,220), small)

    if paused or game_over or won:
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,160)); screen.blit(overlay, (0,0))
        title = 'PAUSED' if paused else ('LAWN SAVED!' if won else 'ZOMBIES ATE YOUR LAWN!')
        surf = big.render(title, True, (255,235,125))
        screen.blit(surf, ((W - surf.get_width()) // 2, 295))
        text('Press P to resume' if paused else 'Press R to play again', 440, 370)
    pygame.display.flip()

running = True
while running:
    dt = min(clock.tick(60) / 1000, .05)
    mx, my = pygame.mouse.get_pos()

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.WINDOWFOCUSLOST and not (game_over or won):
            paused = True
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE: running = False
            if e.key == pygame.K_r: reset()
            if e.key == pygame.K_p and not (game_over or won): paused = not paused
            if pygame.K_1 <= e.key <= pygame.K_6: selected = e.key - pygame.K_1
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not (game_over or won or paused):
            collected = False
            if my > 150:
                for s in suns[:]:
                    if math.hypot(mx - s.x, my - s.y) < 30:
                        money += s.value; suns.remove(s); collected = True
            if collected:
                continue
            for i in range(len(CARDS)):
                if CARD_RECTS[i].collidepoint(mx, my):
                    selected = i
                    break
            cell = cell_at(mx, my)
            if cell:
                row, col = cell
                name, cost, cool = CARDS[selected]
                if (row, col) not in plants and money >= cost and cd[selected] <= 0:
                    plants[(row, col)] = Plant(name, row, col,
                                               450 if name == 'Wall' else 95,
                                               BOMB_FUSE if name == 'Bomb' else 0)
                    money -= cost; cd[selected] = cool

    hover = cell_at(mx, my)
    update(dt)
    draw()

pygame.quit()
sys.exit()
