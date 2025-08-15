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
using Util;
using MAI2.Util;

[assembly: MelonInfo(typeof(default_namespace.Dump_notes), "Dump_Notes", "1.0.0", "Simon273")]
[assembly: MelonGame("sega-interactive", "Sinmai")]

namespace default_namespace {
    public class Dump_notes : MelonMod
    {
        private static FieldInfo _activeNoteListField;
        private static bool _fieldsInitialized = false;
        private static string _outputFilePath = "";
        private static bool _isFileCreated = false;
        private static bool _isDumpEnabled = false;
    // 注: 使用 GetKeyDown 进行边沿触发，不再需要上一帧状态
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
            
            // StarNote相关属性
            public Vector3 StarLocalScale { get; set; }         // StarNote的localScale
            public float UserNoteSize { get; set; }             // 用户设置的音符大小
        }

        public override void OnInitializeMelon()
        {
            HarmonyInstance.PatchAll(typeof(Dump_notes));
            MelonLogger.Msg($"Load success.");
            MelonLogger.Msg($"  I键: 切换音符数据导出 (默认关闭)");
            MelonLogger.Msg($"  K键: 打印游戏结束状态调试信息");
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
                // 不在这里创建文件，仅在真正开始导出并写入首帧时延迟创建
                _isFileCreated = false;
                
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
                Vector2 holdBodySize = Vector2.zero;
                Vector3 starLocalScale = Vector3.zero;
                float userNoteSize = 1f;

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
                
                // 处理StarNote尺寸
                else if (noteType.Contains("Star"))
                {
                    // 获取NoteObj的localScale
                    starLocalScale = noteObj.transform.localScale;
                    
                    // 获取用户设置的音符大小
                    try
                    {
                        if (GamePlayManager.Instance != null)
                        {
                            userNoteSize = GamePlayManager.Instance.GetGameScore(0).UserOption.NoteSize.GetValue();
                        }
                    }
                    catch
                    {
                        userNoteSize = 1f; // 默认值
                    }
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

                    // touch/hold/star尺寸数据
                    TouchDecorPosition = touchDecorPosition,
                    HoldBodySize = holdBodySize,
                    StarLocalScale = starLocalScale,
                    UserNoteSize = userNoteSize
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
                    var desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
                    var timestamp = DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
                    var musicID = _currentMusicInfo[0];
                    _outputFilePath = Path.Combine(desktopPath, $"{musicID}_{timestamp}.txt");

                    // 创建文件并写入头部信息
                    File.WriteAllText(_outputFilePath, $"Note Dump Started at {timestamp}\n");
                    File.AppendAllText(_outputFilePath, $"Music Info: {string.Join(" - ", _currentMusicInfo)}\n");
                    File.AppendAllText(_outputFilePath, "Format: Type-Index | PosX, PosY | LocalX, LocalY | Status | AppearMsec | (TouchDecor/HoldSize/StarScale+UserNoteSize)\n");
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
                    // star尺寸信息
                    else if (note.NoteType.Contains("Star"))
                    {
                        line += $" | StarScale: {note.StarLocalScale.x:F4},{note.StarLocalScale.y:F4} | UserNoteSize: {note.UserNoteSize:F4}";
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
            // 边沿触发：按下一次 I 键，切换导出开关
            if (Input.GetKeyDown(KeyCode.I))
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
        }

        // 热键调试：K键打印游戏结束状态
        [HarmonyPostfix]
        [HarmonyPatch(typeof(GameProcess), "OnUpdate")]
        public static void GameProcess_OnUpdate_Debug(GameProcess __instance)
        {
            try
            {
                // 检测 K 键按下
                if (Input.GetKeyDown(KeyCode.K))
                {
                    MelonLogger.Msg("=== 游戏结束状态调试信息 ===");
                    
                    // 获取GameMonitor数组
                    var monitorsField = typeof(GameProcess).GetField("_monitors", BindingFlags.NonPublic | BindingFlags.Instance);
                    var monitors = (Monitor.GameMonitor[])monitorsField.GetValue(__instance);
                    
                    if (monitors != null)
                    {
                        for (int i = 0; i < monitors.Length; i++)
                        {
                            if (monitors[i] != null)
                            {
                                var monitorIndex = i;
                                var gameScore = MAI2.Util.Singleton<GamePlayManager>.Instance.GetGameScore(monitorIndex);
                                
                                MelonLogger.Msg($"--- 玩家 {i + 1} 状态 ---");
                                MelonLogger.Msg($"  IsAllJudged: {gameScore.IsAllJudged()}");
                                MelonLogger.Msg($"  IsTrackSkip: {gameScore.IsTrackSkip}");
                                MelonLogger.Msg($"  IsEnable: {gameScore.IsEnable}");
                                MelonLogger.Msg($"  Life: {gameScore.Life}");
                                
                                // 检查音符判定状态
                                var judgeResultListField = gameScore.GetType().GetField("_judgeResultList", BindingFlags.NonPublic | BindingFlags.Instance);
                                if (judgeResultListField != null)
                                {
                                    var judgeResults = judgeResultListField.GetValue(gameScore);
                                    if (judgeResults != null)
                                    {
                                        var resultsArray = judgeResults as Array;
                                        if (resultsArray != null)
                                        {
                                            int totalNotes = resultsArray.Length;
                                            int judgedNotes = 0;
                                            
                                            for (int j = 0; j < resultsArray.Length; j++)
                                            {
                                                var result = resultsArray.GetValue(j);
                                                var judgedField = result.GetType().GetField("Judged");
                                                if (judgedField != null && (bool)judgedField.GetValue(result))
                                                {
                                                    judgedNotes++;
                                                }
                                            }
                                            
                                            MelonLogger.Msg($"  音符状态: {judgedNotes}/{totalNotes} 已判定");
                                        }
                                    }
                                }
                                
                                // 检查对象状态
                                var isAllObjectEnd = monitors[i].IsAllObjectEnd();
                                var isAnyObjectActiveField = typeof(Monitor.GameMonitor).GetField("IsAnyObjectActive", BindingFlags.NonPublic | BindingFlags.Instance);
                                var isAnyObjectActive = isAnyObjectActiveField?.GetValue(monitors[i]) as bool? ?? false;
                                
                                MelonLogger.Msg($"  IsAllObjectEnd: {isAllObjectEnd}");
                                MelonLogger.Msg($"  IsAnyObjectActive: {isAnyObjectActive}");
                            }
                        }
                    }
                    
                    // 检查音乐状态
                    MelonLogger.Msg($"--- 音乐状态 ---");
                    MelonLogger.Msg($"  IsEndMusic: {Manager.SoundManager.IsEndMusic()}");
                    MelonLogger.Msg($"  IsPlayingMusic: {!Manager.SoundManager.IsEndMusic()}");
                    
                    // 检查当前游戏序列
                    var sequenceField = typeof(GameProcess).GetField("_sequence", BindingFlags.NonPublic | BindingFlags.Instance);
                    if (sequenceField != null)
                    {
                        var sequence = sequenceField.GetValue(__instance);
                        MelonLogger.Msg($"  当前游戏序列: {sequence}");
                    }
                    
                    // 检查当前时间
                    var currentTime = Manager.NotesManager.GetCurrentMsec();
                    MelonLogger.Msg($"  当前游戏时间: {currentTime:F2}ms");
                    
                    MelonLogger.Msg("=== 调试信息结束 ===");
                }
            }
            catch (Exception e)
            {
                MelonLogger.Error($"调试信息获取失败: {e.Message}");
            }
        }
    }
}
