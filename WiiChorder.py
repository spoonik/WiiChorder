import os
from pathlib import Path
import random
import sys
import time

import mido
from mido import Message
import pygame
from pygame.locals import *

# for RasPi pygame issue: https://qiita.com/NNNGriziMan/items/65191ed1c24f530810c3
os.environ["SDL_VIDEODRIVER"] = "dummy"


# 再生中か、再生停止かを設定
PLAYBACK_ON = True

def local_print(str):
    if False:
        print(str)


# Button Mapping source: https://heavymoon.org/2022/12/03/8bitdo-ns30pro/
PAD_BUTTON_START     =  11
PAD_BUTTON_SELECT    =  10
PAD_BUTTON_A         =  0
PAD_BUTTON_B         =  1
PAD_BUTTON_X         =  3
PAD_BUTTON_Y         =  4
PAD_BUTTON_L1        =  6
PAD_BUTTON_R1        =  7
PAD_BUTTON_L2        =  8
PAD_BUTTON_R2        =  9
PAD_AXIS_LEFT_HORIZONTAL  = 0
PAD_AXIS_LEFT_VERTICAL    = 1
PAD_AXIS_RIGHT_HORIZONTAL = 3
PAD_AXIS_RIGHT_VERTICAL   = 4
SHIFT_KEY_ON = False        # Shiftキーの定義


def process_gamepad_event():
    global SHIFT_KEY_ON
    eventlist = pygame.event.get()
    for e in eventlist:
        if e.type == pygame.locals.JOYBUTTONDOWN:
            if e.button == PAD_BUTTON_SELECT:
                input_mapper("Select", SHIFT_KEY_ON)
            elif e.button == PAD_BUTTON_START:
                input_mapper("Start", SHIFT_KEY_ON)
            elif e.button == PAD_BUTTON_B:
                SHIFT_KEY_ON = True
                local_print("Shift On")
            elif e.button == PAD_BUTTON_A:
                input_mapper("A", SHIFT_KEY_ON)
            elif e.button == PAD_BUTTON_Y:
                input_mapper("Y", SHIFT_KEY_ON)
            elif e.button == PAD_BUTTON_X:
                input_mapper("X", SHIFT_KEY_ON)
            elif e.button == PAD_BUTTON_L1:
                input_mapper("L1", SHIFT_KEY_ON)
            elif e.button == PAD_BUTTON_R1:
                input_mapper("R1", SHIFT_KEY_ON)
            elif e.button == PAD_BUTTON_L2:
                input_mapper("L2", SHIFT_KEY_ON)
            elif e.button == PAD_BUTTON_R2:
                input_mapper("R2", SHIFT_KEY_ON)

        elif e.type == pygame.locals.JOYAXISMOTION:
            if e.axis == PAD_AXIS_LEFT_HORIZONTAL:
                if abs(e.value) > 0.5:
                    local_print(f"axis L H {e.value}")
                    make_sus2_4(4)  # Joy L : right
                elif abs(e.value) < -0.5:
                    local_print(f"axis L H {e.value}")
                    make_sus2_4(2)  # Joy L : left
                else:
                    make_sus2_4(0)
            elif e.axis == PAD_AXIS_LEFT_VERTICAL:
                if abs(e.value) > 0.5:
                    local_print(f"axis L V {e.value}")
                    make_semitone_slide(1)
                elif abs(e.value) < -0.5:
                    local_print(f"axis L V {e.value}")
                    make_semitone_slide(-1)
                else:
                    make_semitone_slide(0)                    
            elif e.axis == PAD_AXIS_RIGHT_HORIZONTAL:
                local_print(f"axis R H {e.value}")
                shift_midi_range(e.value, "H")
            elif e.axis == PAD_AXIS_RIGHT_VERTICAL:
                local_print(f"axis R V {e.value}")
                shift_midi_range(e.value, "V")

        elif e.type == pygame.locals.JOYHATMOTION:
            if e.value[0] > 0:
                input_mapper("Right", SHIFT_KEY_ON)
            if e.value[0] < 0:
                input_mapper("Left", SHIFT_KEY_ON)
            if e.value[1] > 0:
                input_mapper("Up", SHIFT_KEY_ON)
            if e.value[1] < 0:
                input_mapper("Down", SHIFT_KEY_ON)

        elif e.type == pygame.locals.JOYBUTTONUP:
            if e.button == PAD_BUTTON_B:    # その他のボタンUPにはあまり興味ない
                SHIFT_KEY_ON = False
                local_print("Shift Off")


# グローバル定数 ==================================================================================
MIDIROOT = 60
SEQUENCE_LEN = 16       # シーケンスの長さ
BUTTON_PROCESS_INTERVAL = 0.1   # ボタン反応を待つインターバル。不要かも [TODO]
MIN_TEMPO = 2.5     # Hz
MAX_TEMPO = 8.0     # Hz
TEMPO_RATE = 0.025   # テンポUp／Downのレート
ARP_TEMPLATE = ["UP", "DOWN", "RND"]

# 12半音。特に定義する必要はないのだけど。SCALE_ID[0] = 0 = "C" を表している
SCALE_ID = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

# 上記 SCALE_ID に対応するキー音名と、コードの表記
KEY_NAME = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
CHORD_ROMAN = ["I", "I#", "ii", "IIIb", "iii", "IV", "iv#", "V", "VIb", "vi", "VIIb", "vii"]

# 上記 SCALE_ID でメジャースケール、またはマイナースケールで使う音
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [9, 11, 0, 2, 4, 5, 7]

# 上記 SCALE_ID での各スケールIDにそれぞれ対応するコード
CHORDS = {
    0: [0, 4, 7, 11],   # I (eg. "C")
    1: [1, 5, 8, 11],   # I#
    2: [2, 5, 9, 0],    # ii(m)
    3: [3, 7, 10, 2],   # IIIb
    4: [4, 7, 11, 2],   # iii(m)
    5: [5, 9, 0, 4],    # IV
    6: [6, 9, 1, 4],    # iv#(m)
    7: [7, 11, 2, 5],   # V
    8: [8, 0, 3, 7],    # VIb
    9: [9, 0, 4, 7],    # vi(m)
    10: [10, 2, 5, 9],  # VIIb
    11: [11, 2, 5, 9],  # viim-5
}


# グローバル変数 (説明は、Cmajスケールが設定されているとき) =========================================
CUR_CHORD_TONE_NUM = 3      # 3:Triad or 4:Seventh
CUR_SCALE_ROOT = 0          # 0->"Cmajスケール"、4->"Emajスケール"
CUR_CHORD_IDX = 0           # eg) CUR_SCALE_ROOT=4(Emaj Scale)で、CUR_CHORD_IDX=4(iii)だったら
                            #     Emaj の iii なので G#min を表す

# 現在の上下へのMIDIシーケンスの音の利用可能領域(24 = 2oct)
MIDIRANGE_BASE = 16
MAXMIDIRANGE_BASE = 28
CUR_MIDIRANGE = 24

# 現在の MajorScaleのRoot X 現在のコードを加味して
# C(MIDI 60)との偏位で、シーケンスパターンを構成する
CUR_SEQUENCE = [0] * SEQUENCE_LEN
CUR_MIDI_SEQ = [0] * SEQUENCE_LEN

# テンポ (bps=Hz) Beat par secondに注意！ MIDIノートを鳴らす速さである
CUR_TEMPO = 3.6


# シーケンスパターンのコントロール ===============================================================
# 各コード内の音をどの順番で鳴らすか、を定義するアルペジオパターン
ARP_PATTERN_TRIAD = [0] * SEQUENCE_LEN
OCTSHIFT_PATTERN_TRIAD = [0] * SEQUENCE_LEN
ARP_PATTERN_SEVENTH = [0] * SEQUENCE_LEN
OCTSHIFT_PATTERN_SEVENTH = [0] * SEQUENCE_LEN


# プリミティブなユーティリティ関数 ===============================================================
# 各種のIDXを0〜11に正規化するユーティリティ
def in_scale(n):
    return (n+12) % 12
# MIDIノートを発音するためのユーティリティ
def play_one_note(midi_port, note):
    global PLAYBACK_ON, CUR_TEMPO, BUTTON_PROCESS_INTERVAL
    interval = 1.0 / CUR_TEMPO - BUTTON_PROCESS_INTERVAL
    if PLAYBACK_ON:        # MIDIノートの発音
        midi_port.send(Message('note_on', note=note, velocity=100))
        time.sleep(interval)
        midi_port.send(Message('note_off', note=note))
    else:
        time.sleep(interval)


MIDI_HIGHEST = MIDIROOT + MIDIRANGE_BASE
MIDI_LOWEST = MIDIROOT - MIDIRANGE_BASE
# 下記で生成した CUR_SEQUENCE をMIDI Note番号のシーケンス(演奏可能)に変換する
def get_midi_seq():
    global CUR_SEQUENCE, CUR_MIDI_SEQ, MIDIROOT, MIDI_HIGHEST, MIDI_LOWEST
    for i in range(SEQUENCE_LEN):
        tmp_note = CUR_SEQUENCE[i] + MIDIROOT
        if tmp_note < MIDI_LOWEST:
            tmp_note += 12
        elif tmp_note > MIDI_HIGHEST:
            tmp_note -= 12
        CUR_MIDI_SEQ[i] = tmp_note
    return CUR_MIDI_SEQ


CUR_SUS = 0
CUR_SLIDE = 0
# SUS2/4, SLIDEを加味してコードのSeedを返す
def get_modulated_seed_chord():
    global CUR_CHORD_IDX, CUR_SUS
    chord = CHORDS[CUR_CHORD_IDX]
    
    if CUR_SLIDE > 0:       # 半音上にスライド
        for i in range(len(chord)):
            chord[i] += 1
    elif CUR_SLIDE < 0:     # 半音下にスライド
        for i in range(len(chord)):
            chord[i] -= 1

    if CUR_SUS == 2:        # sus2にする
        chord[1] = chord[0]+2
    elif CUR_SUS == 4:      # sus4にする
        chord[1] = chord[2]-2

    # 正規化
    for i in range(len(chord)):
        chord[i] = in_scale(chord[i])
    return chord


# コード進行しても、アルペジオのパターンは変化しないで、持続感があるように、
# 「現在のコード」に対して、シーケンスにはどの「構成音のINDEXが」「どういうオクターブシフトして」
# 演奏されるべきかをRefreshする
CUR_ARP_PATTERN = 0
def toggle_arp_pattern(pattern=None):
    global SEQUENCE_LEN, ARP_PATTERN_TRIAD, ARP_PATTERN_SEVENTH, OCTSHIFT_PATTERN_SEVENTH, OCTSHIFT_PATTERN_TRIAD, CUR_ARP_PATTERN
    # 現在のコードの、Rootからの変位を、2オクターブ内でシフトしながら、ランダムに並べ替える
    triad_i = 0
    seventh_i = 0

    if pattern is not None:
        CUR_ARP_PATTERN = pattern
    else:   # 基本はUP/DOWN/RANDOM の3種類でアルペジオパターンをトグル
        CUR_ARP_PATTERN = (CUR_ARP_PATTERN+1) % 3

    if CUR_ARP_PATTERN == 0:    # UP ARPPEGIO
        for i in range(SEQUENCE_LEN):
            ARP_PATTERN_SEVENTH[i] = i % 4
            OCTSHIFT_PATTERN_SEVENTH[i] = (int(i/4) - 2) * 12
            ARP_PATTERN_TRIAD[i] = i % 3
            OCTSHIFT_PATTERN_TRIAD[i] = (int(i/3) - 3) * 12
    elif CUR_ARP_PATTERN == 1:  # DOWN ARPPEGIO
        for i in range(SEQUENCE_LEN):
            ARP_PATTERN_SEVENTH[i] = 3 - i % 4
            OCTSHIFT_PATTERN_SEVENTH[i] = (2 - int(i/4)) * 12
            ARP_PATTERN_TRIAD[i] = 2 - i % 3
            OCTSHIFT_PATTERN_TRIAD[i] = (2 - int(i/3)) * 12
    else:       # RANDOM ARPPEGIO
        while True:
            tmptone = random.randint(0, 3)  # 一回Seventh用のRandを作って
            if seventh_i < SEQUENCE_LEN:
                ARP_PATTERN_SEVENTH[seventh_i] = tmptone
                OCTSHIFT_PATTERN_SEVENTH[seventh_i] = random.randint(-1, 1) * 12
                seventh_i += 1
            if tmptone != 3:
                ARP_PATTERN_TRIAD[triad_i] = random.randint(0, CUR_CHORD_TONE_NUM-1)
                OCTSHIFT_PATTERN_TRIAD[triad_i] = random.randint(-1, 1) * 12
                triad_i += 1
                if triad_i >= SEQUENCE_LEN:
                    break


# 上記で定義された「ARP_PATTERN」と「OCTSHIFT_PATTERN」を組み合わせて、MIDIシーケンスパターンにする
# ただし、まだMIDIノート番号は加味されてない。C=60からの差分のみである
def update_sequence_pattern():
    global CUR_CHORD_IDX, SEQUENCE_LEN, CUR_SEQUENCE, ARP_PATTERN_TRIAD, ARP_PATTERN_SEVENTH, CUR_SCALE_ROOT, OCTSHIFT_PATTERN_SEVENTH, OCTSHIFT_PATTERN_TRIAD, CUR_MIDI_SEQ
    seed_chord = get_modulated_seed_chord()
    for i in range(SEQUENCE_LEN):
        if CUR_CHORD_TONE_NUM == 4:
            CUR_SEQUENCE[i] = in_scale(seed_chord[ARP_PATTERN_SEVENTH[i]] + CUR_SCALE_ROOT) + OCTSHIFT_PATTERN_SEVENTH[i]
        else:
            CUR_SEQUENCE[i] = in_scale(seed_chord[ARP_PATTERN_TRIAD[i]] + CUR_SCALE_ROOT) + OCTSHIFT_PATTERN_TRIAD[i]
    # MIDI Note Numberに変換
    CUR_MIDI_SEQ = get_midi_seq()
    local_print(f"Chord Changed to {KEY_NAME[in_scale(CUR_CHORD_IDX+CUR_SCALE_ROOT)]} ({CHORD_ROMAN[CUR_CHORD_IDX]}) in Scale {KEY_NAME[CUR_SCALE_ROOT]}")
    return CUR_SEQUENCE, CUR_MIDI_SEQ


# コードチェンジのコントロール =====================================================================
def chord_change_by_semitone(dif):
    global CUR_CHORD_IDX, MAJOR_SCALE
    CUR_CHORD_IDX = in_scale(CUR_CHORD_IDX + dif)
    update_sequence_pattern()

def chord_change_by_scale(scale_dif):
    global CUR_CHORD_IDX, MAJOR_SCALE
    cur_chord_root = CUR_CHORD_IDX
    if CUR_CHORD_IDX not in MAJOR_SCALE:
        cur_chord_root += 1
    next_chord_root = (MAJOR_SCALE.index(cur_chord_root) + scale_dif + len(MAJOR_SCALE)) % len(MAJOR_SCALE)
    CUR_CHORD_IDX = MAJOR_SCALE[next_chord_root]
    update_sequence_pattern()


# コードチェンジの入力受付コマンド ==================================================================
def chord_up4(shift_key):        # 4度上(shift半音)のコードに進行: Up Button
    if shift_key:
        chord_change_by_semitone(1)
    else:
        chord_change_by_scale(3)

def chord_down4(shift_key):      # 4度下(shift半音)のコードに進行: Down Button
    if shift_key:
        chord_change_by_semitone(-1)
    else:
        chord_change_by_scale(-3)

def chord_up2(shift_key):        # 2度上(shift3度)のコードに進行: Right Arrow Button
    if shift_key:
        chord_change_by_scale(2)
    else:
        chord_change_by_scale(1)

def chord_down2(shift_key):      # 2度下(shift3度)のコードに進行: Left Arrow Button
    if shift_key:
        chord_change_by_scale(-2)
    else:
        chord_change_by_scale(-1)

def tempo_change(shift_key):
    global CUR_TEMPO, MIN_TEMPO, MAX_TEMPO
    if shift_key:
        if CUR_TEMPO > MIN_TEMPO:
            CUR_TEMPO = max(CUR_TEMPO * (1.0-TEMPO_RATE), MIN_TEMPO)
    else:
        if CUR_TEMPO < MAX_TEMPO:
            CUR_TEMPO = min(CUR_TEMPO * (1.0+TEMPO_RATE), MAX_TEMPO)
    local_print(f"Tempo {'Down' if shift_key else 'Up'} to {CUR_TEMPO}")


# 転調のコントロール ============================================================================
def transpose(dif):
    # 現在のスケールを"dif"x半音分だけ上に転調し、現在のコードをスケール上の最も近いコードに変換する
    global CUR_CHORD_IDX, CUR_SCALE_ROOT, MAJOR_SCALE
    CUR_SCALE_ROOT = in_scale(CUR_SCALE_ROOT + dif)
    if abs(dif) > 1:
        CUR_CHORD_IDX = in_scale(CUR_SCALE_ROOT - dif)
    if CUR_CHORD_IDX not in MAJOR_SCALE:
        CUR_CHORD_IDX -= 1
    local_print(f"Transpose to {KEY_NAME[CUR_SCALE_ROOT]}, Chord mod to {CHORD_ROMAN[CUR_CHORD_IDX]}")
    update_sequence_pattern()

def transpose_5th_up(shift_key):     # 5度上(shift:短3度)転調: ZR1 Button
    up = 3 if shift_key else 7
    transpose(up)
def transpose_5th_down(shift_key):   # 5度下(shift:長3度)転調: ZL1 Button
    down = -4 if shift_key else -7
    transpose(down)
def transpose_semi_up(shift_key):    # 半音上(shift:1度)転調: ZR1 Button
    up = 2 if shift_key else 1
    transpose(up)
def transpose_semi_down(shift_key):  # 半音下(shift:1度)転調: ZL1 Button
    down = -2 if shift_key else -1
    transpose(down)


# シーケンスのコントロール =======================================================================
def toggle_triad_seventh(shift_key): # 三和音と四話音を切り替え: A Button
    global CUR_CHORD_TONE_NUM, CUR_CHORD_IDX
    CUR_CHORD_TONE_NUM = 4 if CUR_CHORD_TONE_NUM==3 else 3
    if shift_key:   # 現在のスケール内のコードルートにリセットする
        if CUR_CHORD_IDX not in MAJOR_SCALE:
            CUR_CHORD_IDX = in_scale(CUR_CHORD_IDX + 1)
    update_sequence_pattern()


def change_arp_pattern(shift_key):    # アルペジオパターンを切り替え: X Button
    if shift_key:
        toggle_arp_pattern(CUR_ARP_PATTERN)
    else:
        toggle_arp_pattern()
    update_sequence_pattern()


# スティックによる一時的な変調 ====================================================================
def make_sus2_4(sus_val): # sus2, sus4に変調: L Stick right/left 
    global CUR_SUS
    if CUR_SUS == sus_val:
        return
    CUR_SUS = sus_val
    update_sequence_pattern()

def make_semitone_slide(slide_val): # 半音上・下に変調: L Stick down/up 
    global CUR_SLIDE
    if CUR_SLIDE == slide_val:
        return
    CUR_SLIDE = slide_val
    update_sequence_pattern()

def shift_midi_range(ratio, h_v_key): # MIDI音域を高音・低音にシフト: R Stick right/left 
    global MIDI_HIGHEST, MIDI_LOWEST, CUR_MIDIRANGE
    if h_v_key == "H":
        if abs(ratio) > 0.5:
            MIDI_HIGHEST = MIDIROOT + int(MAXMIDIRANGE_BASE * ratio)
            MIDI_LOWEST = MIDIROOT - int(MAXMIDIRANGE_BASE * ratio)
            CUR_MIDIRANGE = MIDI_HIGHEST - MIDI_LOWEST
        else:
            CUR_MIDIRANGE = MIDIRANGE_BASE
    elif h_v_key == "V":
        if abs(ratio) > 0.5:
            MIDI_HIGHEST = MIDIROOT + int(CUR_MIDIRANGE / 2 * ratio)
            MIDI_LOWEST = MIDIROOT - int(CUR_MIDIRANGE / 2 * ratio)
        else:
            MIDI_HIGHEST = MIDIROOT + MIDIRANGE_BASE
            MIDI_LOWEST = MIDIROOT - MIDIRANGE_BASE            
    update_sequence_pattern()


# アプリ全体のコントロール =======================================================================
def play_note_toggle(shift_key):     # シーケンスをスタート・ポーズする: Start Button
    global PLAYBACK_ON, TERMINATE_VALUE
    PLAYBACK_ON = not PLAYBACK_ON
    local_print(f"Playback: {PLAYBACK_ON}")
    TERMINATE_VALUE = 0

# [TODO] Shift + Select Button to TERMINATE APP (WARNING)
# "SELECT" を連続4回押すと、Terminate (exit) する仕様とする
TERMINATE_VALUE = 0
def terminate_app(shift_key):
    global TERMINATE_VALUE
    TERMINATE_VALUE += 1
    if TERMINATE_VALUE > 4:
        sys.exit()


# 関数と入力キーの紐付け ========================================================================
KEY_MAPPER = {
    "Select": terminate_app,
    "Start": play_note_toggle,
    "A": toggle_triad_seventh,
    "X": change_arp_pattern,
    "Y": tempo_change,
    "Up": chord_up4,
    "Down": chord_down4,
    "Right": chord_up2,
    "Left": chord_down2,
    "L1": transpose_5th_down,
    "R1": transpose_5th_up,
    "L2": transpose_semi_down,
    "R2": transpose_semi_up
}


def input_mapper(key, shift_key):
    local_print(key)
    if key in KEY_MAPPER:
        KEY_MAPPER[key](shift_key)

# ライフチェック用の.runningファイルの更新
LIFE_CHECK_CLOCK = 0
RUNNING_FILE = '/home/pi/Public/.running'
def touch_running_file():
    global LIFE_CHECK_CLOCK
    file_path = Path(RUNNING_FILE).expanduser()
    if file_path.exists():
        os.utime(file_path, None)
    else:
        if LIFE_CHECK_CLOCK == 0:
            file_path.touch()
        LIFE_CHECK_CLOCK += 1
        if LIFE_CHECK_CLOCK > int(CUR_TEMPO * 60):
            LIFE_CHECK_CLOCK = 0
        
def remove_running_file():
    file_path = Path(RUNNING_FILE).expanduser()
    if file_path.exists():
        os.remove(RUNNING_FILE)


def main():
    remove_running_file()

    # MIDIシーケンス初期化
    toggle_arp_pattern(0)
    update_sequence_pattern()
    ports = None
    joy = None

    try:    # MIDIポート・pygameの初期化
        ports = mido.get_output_names()
        print(f"MIDI Ports are: {ports}")
        pygame.init()
        pygame.joystick.init()
    except Exception as e:
        print("\007")   #Beep
        return

    # Ports: Mac=> 1=IAC(Internal)/ 2=USB, RasPi=> 1=USB
    with mido.open_output(ports[1]) as midi_port:
        while True:         # 基本起きっぱなしにしとく
            try:
                while True:     # ゲームコントローラの接続が切れた時、再度見つかるまでループ
                    joysticks = pygame.joystick.get_count()
                    if joysticks >= 1:
                        print(f"JoyStick num: {joysticks}")
                        break
                    else:
                        remove_running_file()
                    time.sleep(10)

                joy = pygame.joystick.Joystick(0)
                joy.init()

                while True:
                    midi_seq = get_midi_seq()
                    for i in range(SEQUENCE_LEN):
                        play_one_note(midi_port, midi_seq[i])    # MIDI演奏
                        process_gamepad_event()    # ゲームコントローラ入力の処理
                        time.sleep(BUTTON_PROCESS_INTERVAL)
                        touch_running_file()

            except Exception as e:
                remove_running_file()
                print("\007")   #Beep
                continue


if __name__ == '__main__':
    main()
