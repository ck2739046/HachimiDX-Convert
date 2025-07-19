using HarmonyLib;
using MelonLoader;
using UnityEngine;
using System;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using System.IO;
using Monitor;
using Monitor.Game;
using Manager;
using Main;
using Process;
using DB;

[assembly: MelonInfo(typeof(default_namespace.Dump_notes), "Dump_Notes", "1.0.0", "Simon273")]
[assembly: MelonGame("sega-interactive", "Sinmai")]

namespace default_namespace {
    public class Dump_notes : MelonMod
    {
        private static FieldInfo _activeNoteListField;
        private static bool _fieldsInitialized = false;
        private static string _outputFilePath = "";
        private static bool _isFileCreated = false;
        private static bool _isDumpEnabled = true;
        private static bool _lastKeyState = false; // 上一帧按键状态 
        private static List<string> _currentMusicInfo = new List<string> { "Unknown" };
        private static bool _gameStartDetected = false; // 乐曲开始标志

        public class NoteInfo
        {
            public string NoteType { get; set; }
            public int NoteIndex { get; set; }
            public Vector3 Position { get; set; }
            public Vector3 LocalPosition { get; set; }
            public string Status { get; set; }
            public bool IsActive { get; set; }
            public bool IsEnd { get; set; }
            public float AppearMsec { get; set; }

            // 尺寸相关属性
            public Vector3 TouchDecorPosition { get; set; }  // Touch装饰位置
            public Vector2 HoldBodySize { get; set; }           // Hold尺寸
        }

        public override void OnInitializeMelon()
        {
            HarmonyInstance.PatchAll(typeof(Dump_notes));
            MelonLogger.Msg($"Load success. Press I to toggle note dumping.");
        }

        static void InitializeFields()
        {
            if (_fieldsInitialized) return;

            var gameCtrlType = typeof(GameCtrl);
            _activeNoteListField = gameCtrlType.GetField("_activeNoteList", BindingFlags.NonPublic | BindingFlags.Instance);

            _fieldsInitialized = true;
        }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(GameProcess), "OnStart")]
        public static void GameProcess_OnStart_Postfix(GameProcess __instance)
        {
            try
            {
                // 获取乐曲信息
                _currentMusicInfo = GetCurrentMusicInfo();
                _gameStartDetected = true;
                MelonLogger.Msg($"track start: {string.Join(" - ", _currentMusicInfo)}");
                // 创建txt
                if (!_isFileCreated)
                {
                    var desktopPath = @"C:\Users\ck273\Desktop";
                    var timestamp = DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
                    var musicID = _currentMusicInfo[0];
                    _outputFilePath = Path.Combine(desktopPath, $"{musicID}_{timestamp}.txt");

                    // 创建文件并写入头部信息
                    File.WriteAllText(_outputFilePath, $"Note Dump Started at {timestamp}\n");
                    File.AppendAllText(_outputFilePath, $"Music Info: {string.Join(" - ", _currentMusicInfo)}\n");
                    File.AppendAllText(_outputFilePath, "Format: Type/Index | PosX, PosY | LocalX, LocalY | Status | AppearMsec | (size for touch/hold)\n");
                    File.AppendAllText(_outputFilePath, "=".PadRight(30, '=') + "\n");

                    _isFileCreated = true;
                    MelonLogger.Msg($"Note dump output file: {_outputFilePath}");
                }
                
            }
            catch (Exception e)
            {
                MelonLogger.Error($"Error getting music info on track start: {e}");
            }
        }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(GameProcess), "OnRelease")]
        public static void GameProcess_OnRelease_Postfix(GameProcess __instance)
        {
            try
            {
                if (_gameStartDetected)
                {
                    // 乐曲结束，重置状态
                    _isFileCreated = false;
                    _gameStartDetected = false;
                    MelonLogger.Msg($"track end, ready for next track.");
                }
            }
            catch (Exception e)
            {
                MelonLogger.Error($"Error on track end: {e}");
            }
        }

        private static List<string> GetCurrentMusicInfo()
        {
            try
            {
                // 获取当前选择的音乐ID (第一个玩家)
                int musicId = GameManager.SelectMusicID[0];

                // 获取音乐数据
                var musicData = DataManager.Instance.GetMusic(musicId);
                if (musicData == null) return new List<string> { "Unknown" };

                // 获取难度信息
                int difficulty = GameManager.SelectDifficultyID[0];
                string[] difficultyNames = { "Basic", "Advanced", "Expert", "Master", "Re:Master" };
                string difficultyName = difficulty < difficultyNames.Length ? difficultyNames[difficulty] : $"Unknown({difficulty})";

                // 构建信息
                string musicName = musicData.name?.str ?? "Unknown";
                return new List<string> { musicId.ToString(), musicName, difficultyName };
            }
            catch (Exception e)
            {
                MelonLogger.Warning($"Failed to get music info: {e.Message}");
                return new List<string> { "Unknown" };
            }
        }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(GameCtrl), "UpdateNotes")]
        public static void GameCtrl_UpdateNotes_Postfix(GameCtrl __instance)
        {
            try
            {
                InitializeFields();
                if (!_isDumpEnabled) return;
                DumpAllNotePositions(__instance);
            }
            catch (Exception e)
            {
                MelonLogger.Error($"Error in note dumping: {e}");
            }
        }

        private static void DumpAllNotePositions(GameCtrl gameCtrl)
        {
            var allNotes = new List<NoteInfo>();

            // 获取当前游戏时间
            var currentTime = NotesManager.GetCurrentMsec();

            // 获取活跃音符列表
            if (_activeNoteListField != null)
            {
                var activeNoteList = (List<NoteBase>)_activeNoteListField.GetValue(gameCtrl);
                if (activeNoteList != null)
                {
                    foreach (var note in activeNoteList)
                    {
                        if (note != null && note.gameObject.activeSelf)
                        {
                            // 获取音符
                            string typeName = note.GetType().Name;
                            var noteInfo = GetNoteInfo(note, typeName);
                            if (noteInfo != null)
                                allNotes.Add(noteInfo);
                        }
                    }
                }
            }

            // 如果有音符，则打印信息
            if (allNotes.Count > 0)
            {
                PrintNoteFrame(currentTime, allNotes);
            }
        }

        private static NoteInfo GetNoteInfo(NoteBase noteBase, string noteType)
        {
            try
            {
                var gameObject = noteBase.gameObject;

                // 获取实际的音符位置
                Vector3 actualPosition = Vector3.zero;
                Vector3 actualLocalPosition = Vector3.zero;

                // 通过反射获取 NoteObj
                var noteObjField = noteBase.GetType().GetField("NoteObj", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                var noteObj = noteObjField.GetValue(noteBase) as GameObject;
                actualPosition = noteObj.transform.position;
                actualLocalPosition = noteObj.transform.localPosition;

                // 初始化尺寸数据
                Vector3 touchDecorPosition = Vector3.zero;
                Vector3 touchOverallScale = Vector3.zero;
                Vector2 holdBodySize = Vector2.zero;
                bool isBodyActive = false;

                // 处理Touch音符尺寸
                if (noteType.Contains("Touch"))
                {
                    // 获取ColorsObject数组
                    var colorsField = noteBase.GetType().GetField("ColorsObject", BindingFlags.NonPublic | BindingFlags.Instance);
                    var colors = colorsField.GetValue(noteBase) as SpriteRenderer[];
                    touchDecorPosition = colors[0].transform.localPosition;
                }
                
                // 处理Hold音符尺寸
                else if (noteType.Contains("Hold"))
                {                    
                    var spriteRenderField = noteBase.GetType().GetField("SpriteRender", BindingFlags.NonPublic | BindingFlags.Instance);
                    var spriteRender = spriteRenderField.GetValue(noteBase) as SpriteRenderer;
                    holdBodySize = spriteRender.size;
                }

                // 获取基本信息
                var noteInfo = new NoteInfo
                {
                    NoteType = noteType,
                    NoteIndex = noteBase.GetNoteIndex(),
                    Position = actualPosition,
                    LocalPosition = actualLocalPosition,
                    Status = noteBase.GetNoteStatus().ToString(),
                    IsActive = gameObject.activeSelf,
                    IsEnd = noteBase.IsEnd(),
                    AppearMsec = -1f,  // 默认值

                    // touch/hold尺寸数据
                    TouchDecorPosition = touchDecorPosition,
                    HoldBodySize = holdBodySize,
                };

                // 通过反射获取AppearMsec
                var appearMsecField = noteBase.GetType().GetField("AppearMsec", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                noteInfo.AppearMsec = (float)appearMsecField.GetValue(noteBase);
                
                return noteInfo;
            }
            catch (Exception e)
            {
                MelonLogger.Warning($"Failed to get note info for {noteType}: {e.Message}");
                return null;
            }
        }

        private static void PrintNoteFrame(float currentTime, List<NoteInfo> notes)
        {
            try
            {
                // 设置输出文件路径（第一帧时）
                if (!_isFileCreated)
                {
                    var desktopPath = @"C:\Users\ck273\Desktop";
                    var timestamp = DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
                    var musicID = _currentMusicInfo[0];
                    _outputFilePath = Path.Combine(desktopPath, $"{musicID}_{timestamp}.txt");

                    // 创建文件并写入头部信息
                    File.WriteAllText(_outputFilePath, $"Note Dump Started at {timestamp}\n");
                    File.AppendAllText(_outputFilePath, $"Music Info: {string.Join(" - ", _currentMusicInfo)}\n");
                    File.AppendAllText(_outputFilePath, "Format: Type-Index | PosX, PosY | LocalX, LocalY | Status | AppearMsec\n");
                    File.AppendAllText(_outputFilePath, "=".PadRight(30, '=') + "\n");

                    _isFileCreated = true;
                    MelonLogger.Msg($"Note dump output file: {_outputFilePath}");
                }

                // 构建数据行
                var lines = new List<string>();
                lines.Add($"Frame:{currentTime:F4}|Count:{notes.Count}");

                foreach (var note in notes.OrderBy(n => n.NoteType).ThenBy(n => n.NoteIndex))
                {
                    // 基础信息
                    var line = $"{note.NoteType}-{note.NoteIndex} | " +
                               $"{note.Position.x:F4}, {note.Position.y:F4} | " +
                               $"{note.LocalPosition.x:F4}, {note.LocalPosition.y:F4} | " +
                               $"{note.Status} | {note.AppearMsec:F4}";

                    // touch尺寸信息
                    if (note.NoteType.Contains("Touch"))
                    {
                        var decorPosition = note.TouchDecorPosition;
                        line += $" | TouchDecorPosition: {decorPosition.y:F4}";
                    }
                    // hold尺寸信息
                    else if (note.NoteType.Contains("Hold"))
                    {
                        line += $" | HoldBodySize: {note.HoldBodySize.y:F4}";
                    }

                    lines.Add(line);
                }

                // 追加到文件
                File.AppendAllLines(_outputFilePath, lines);
            }
            catch (Exception e)
            {
                MelonLogger.Error($"Failed to write note frame to file: {e.Message}");
            }
        }
        
        // 热键监听
        [HarmonyPostfix]
        [HarmonyPatch(typeof(GameMainObject), "Update")]
        public static void OnGameMainObjectUpdate()
        {
            // 检测 I 键按下
            bool currentKeyState = Input.GetKey(KeyCode.I);

            // 检测按键从释放到按下的状态变化（边沿检测）
            if (currentKeyState && !_lastKeyState)
            {
                if (_isDumpEnabled)
                {
                    // 关闭
                    _isDumpEnabled = false;
                    _isFileCreated = false; 
                    MelonLogger.Msg("stop dump notes.");
                }
                else
                {
                    // 开启
                    _isFileCreated = false;
                    _isDumpEnabled = true;
                    MelonLogger.Msg("start dump notes.");
                }
            }
            
            _lastKeyState = currentKeyState;
        }
    }
}
