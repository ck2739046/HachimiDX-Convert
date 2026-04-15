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
        private static FieldInfo _activeSlideListField;
        private static MethodInfo? _touchHoldGetHoldAmountMethod;
        private static bool _fieldsInitialized = false;
        private static bool _touchHoldProgressWarningLogged = false;
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
            public bool IsExNote { get; set; }  // EX音符标志 (适用于Tap、Hold、Break)

            // 尺寸相关属性
            public Vector3 TouchDecorPosition { get; set; }  // Touch装饰位置
            public float TouchAlpha { get; set; }            // Touch音符透明度 (Init->Scale阶段 0->1)
            public float TouchHoldProgress { get; set; }     // TouchHold视觉进度 (0~1)
            public Vector2 HoldBodySize { get; set; }           // Hold尺寸
            public Vector3 HoldLocalScale { get; set; }         // Hold音符的localScale
            public Vector3 TapLocalScale { get; set; }          // Tap音符的localScale (Scale阶段)
            
            // StarNote相关属性
            public Vector3 StarLocalScale { get; set; }         // StarNote的localScale
            public float UserNoteSize { get; set; }             // 用户设置的音符大小
            public bool IsSlideRootStar { get; set; }           // 是否为SlideRoot中的第二段星星
            public float StarAlpha { get; set; }                // 星星透明度（第二段）
            public float StarLaunchMsec { get; set; }           // 星星发射时间（第二段）
            public float StarArriveMsec { get; set; }           // 星星到达时间（第二段）
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
            _activeSlideListField = gameCtrlType.GetField("_activeSlideList", BindingFlags.NonPublic | BindingFlags.Instance);
            _touchHoldGetHoldAmountMethod = typeof(TouchHoldC).GetMethod("GetHoldAmount", BindingFlags.NonPublic | BindingFlags.Instance);

            if (_touchHoldGetHoldAmountMethod == null && !_touchHoldProgressWarningLogged)
            {
                MelonLogger.Warning("TouchHold progress method not found, fallback formula will be used.");
                _touchHoldProgressWarningLogged = true;
            }

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

            // 获取活跃音符列表（第一段星星等）
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
                            var noteInfo = GetNoteInfo(note, typeName, currentTime);
                            if (noteInfo != null)
                                allNotes.Add(noteInfo);
                        }
                    }
                }
            }

            // 获取活跃Slide列表（第二段星星）
            if (_activeSlideListField != null)
            {
                var activeSlideList = _activeSlideListField.GetValue(gameCtrl);
                if (activeSlideList != null)
                {
                    // activeSlideList 是 List<SlideRoot>
                    var slideRootType = activeSlideList.GetType();
                    var countProp = slideRootType.GetProperty("Count");
                    var itemProp = slideRootType.GetProperty("Item");
                    
                    int count = (int)countProp.GetValue(activeSlideList);
                    for (int i = 0; i < count; i++)
                    {
                        var slideRoot = itemProp.GetValue(activeSlideList, new object[] { i });
                        if (slideRoot != null)
                        {
                            var slideNoteInfo = GetSlideRootStarInfo(slideRoot, currentTime);
                            if (slideNoteInfo != null)
                                allNotes.Add(slideNoteInfo);
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

        private static NoteInfo GetNoteInfo(NoteBase noteBase, string noteType, float currentTime)
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

                float appearMsec = GetNoteFieldFloat(noteBase, "AppearMsec", -1f);

                // 初始化尺寸数据
                Vector3 touchDecorPosition = Vector3.zero;
                float touchAlpha = 0f;
                float touchHoldProgress = 0f;
                Vector2 holdBodySize = Vector2.zero;
                Vector3 holdLocalScale = Vector3.zero;
                Vector3 starLocalScale = Vector3.zero;
                Vector3 tapLocalScale = Vector3.zero;
                float userNoteSize = 1f;

                // 处理Touch/Touch-Hold音符尺寸
                if (noteType.Contains("Touch"))
                {
                    // 获取ColorsObject数组
                    var colorsField = noteBase.GetType().GetField("ColorsObject", BindingFlags.NonPublic | BindingFlags.Instance);
                    var colors = colorsField.GetValue(noteBase) as SpriteRenderer[];
                    touchDecorPosition = colors[0].transform.localPosition;
                    // 获取透明度（从第一个ColorsObject获取）
                    touchAlpha = colors[0].color.a;

                    if (noteBase is TouchHoldC)
                    {
                        touchHoldProgress = GetTouchHoldProgress(noteBase, currentTime, appearMsec);
                    }
                }
                // 处理Hold音符尺寸
                else if (noteType.Contains("Hold"))
                {
                    var spriteRenderField = noteBase.GetType().GetField("SpriteRender", BindingFlags.NonPublic | BindingFlags.Instance);
                    var spriteRender = spriteRenderField.GetValue(noteBase) as SpriteRenderer;
                    holdBodySize = spriteRender.size;
                    holdLocalScale = noteObj.transform.localScale;
                }
                // 处理Star音符尺寸
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
                // 处理Tap音符尺寸
                else if (noteType.Contains("Tap") || noteType.Contains("Break"))
                {
                    // 获取NoteObj的localScale
                    tapLocalScale = noteObj.transform.localScale;
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
                    AppearMsec = appearMsec,
                    IsExNote = noteBase.ExNote,  // 获取EX音符标志

                    // touch/hold/tap/star尺寸数据
                    TouchDecorPosition = touchDecorPosition,
                    TouchAlpha = touchAlpha,
                    TouchHoldProgress = touchHoldProgress,
                    HoldBodySize = holdBodySize,
                    HoldLocalScale = holdLocalScale,
                    TapLocalScale = tapLocalScale,
                    StarLocalScale = starLocalScale,
                    UserNoteSize = userNoteSize
                };
                
                return noteInfo;
            }
            catch (Exception e)
            {
                MelonLogger.Warning($"Failed to get note info for {noteType}: {e.Message}");
                return null;
            }
        }

        private static float GetTouchHoldProgress(NoteBase noteBase, float currentTime, float appearMsec)
        {
            if (_touchHoldGetHoldAmountMethod != null)
            {
                try
                {
                    var result = _touchHoldGetHoldAmountMethod.Invoke(noteBase, null);
                    if (result is float value)
                        return ClampProgress(value);
                    if (result is double valueDouble)
                        return ClampProgress((float)valueDouble);
                }
                catch (Exception e)
                {
                    if (!_touchHoldProgressWarningLogged)
                    {
                        MelonLogger.Warning($"TouchHold progress reflection failed, use fallback formula: {e.Message}");
                        _touchHoldProgressWarningLogged = true;
                    }
                    _touchHoldGetHoldAmountMethod = null;
                }
            }

            float tailMsec = GetNoteFieldFloat(noteBase, "TailMsec", appearMsec);
            if (tailMsec <= appearMsec)
                return 0f;

            float progress = (currentTime - appearMsec) / (tailMsec - appearMsec);
            return ClampProgress(progress);
        }

        private static float GetNoteFieldFloat(NoteBase noteBase, string fieldName, float defaultValue)
        {
            var field = noteBase.GetType().GetField(fieldName, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (field == null)
                return defaultValue;

            var value = field.GetValue(noteBase);
            if (value is float floatValue)
                return floatValue;
            if (value is double doubleValue)
                return (float)doubleValue;
            if (value is int intValue)
                return intValue;

            return defaultValue;
        }

        private static float ClampProgress(float value)
        {
            if (float.IsNaN(value) || float.IsInfinity(value))
                return 0f;
            return Mathf.Clamp01(value);
        }

        private static NoteInfo GetSlideRootStarInfo(object slideRoot, float currentTime)
        {
            try
            {
                var slideRootType = slideRoot.GetType();
                
                // 获取_baseStarNote字段
                var baseStarNoteField = slideRootType.GetField("_baseStarNote", BindingFlags.NonPublic | BindingFlags.Instance);
                var baseStarNote = baseStarNoteField?.GetValue(slideRoot) as GameObject;
                
                if (baseStarNote == null || !baseStarNote.activeSelf)
                    return null;

                // 获取BaseSpriteRender
                var baseSpriteRenderField = slideRootType.GetField("BaseSpriteRender", BindingFlags.NonPublic | BindingFlags.Instance);
                var baseSpriteRender = baseSpriteRenderField?.GetValue(slideRoot) as SpriteRenderer;

                // 获取时间信息
                var appearMsecField = slideRootType.GetField("AppearMsec", BindingFlags.NonPublic | BindingFlags.Instance);
                var starLaunchMsecField = slideRootType.GetField("StarLaunchMsec", BindingFlags.NonPublic | BindingFlags.Instance);
                var starArriveMsecField = slideRootType.GetField("StarArriveMsec", BindingFlags.NonPublic | BindingFlags.Instance);
                var noteIndexField = slideRootType.GetField("NoteIndex", BindingFlags.NonPublic | BindingFlags.Instance);
                var endFlagField = slideRootType.GetField("EndFlag", BindingFlags.NonPublic | BindingFlags.Instance);
                var breakFlagField = slideRootType.GetField("BreakFlag", BindingFlags.NonPublic | BindingFlags.Instance);

                float appearMsec = (float)(appearMsecField?.GetValue(slideRoot) ?? 0f);
                float starLaunchMsec = (float)(starLaunchMsecField?.GetValue(slideRoot) ?? 0f);
                float starArriveMsec = (float)(starArriveMsecField?.GetValue(slideRoot) ?? 0f);
                int noteIndex = (int)(noteIndexField?.GetValue(slideRoot) ?? -1);
                bool endFlag = (bool)(endFlagField?.GetValue(slideRoot) ?? false);
                bool breakFlag = (bool)(breakFlagField?.GetValue(slideRoot) ?? false);

                // 判断是否在第二段的可见范围内（从AppearMsec开始，包括缩放淡入阶段）
                if (currentTime < appearMsec)
                    return null;

                // 获取位置和尺寸
                var position = baseStarNote.transform.position;
                var localPosition = baseStarNote.transform.localPosition;
                var localScale = baseStarNote.transform.localScale;
                
                // 获取透明度
                float alpha = baseSpriteRender?.color.a ?? 0f;

                // 确定状态（根据时间判断所处阶段）
                string status;
                if (currentTime < appearMsec)
                    status = "Init";  // AppearMsec之前（实际上已被过滤，不会到达这里）
                else if (currentTime < starLaunchMsec)
                    status = "Scale"; // AppearMsec → StarLaunchMsec：缩放+淡入阶段
                else if (currentTime < starArriveMsec)
                    status = "Move";  // StarLaunchMsec → StarArriveMsec：沿轨迹移动阶段
                else
                    status = "End";   // StarArriveMsec之后：已到达终点

                // 确定类型名称（添加-Move后缀）
                string typeName = breakFlag ? "BreakStarNote-Move" : "StarNote-Move";

                var noteInfo = new NoteInfo
                {
                    NoteType = typeName,
                    NoteIndex = noteIndex,
                    Position = position,
                    LocalPosition = localPosition,
                    Status = status,
                    IsActive = baseStarNote.activeSelf,
                    IsEnd = endFlag,
                    AppearMsec = appearMsec,
                    IsExNote = breakFlag, // Break就是EX

                    // 第二段星星特有数据
                    IsSlideRootStar = true,
                    StarLocalScale = localScale,
                    StarAlpha = alpha,
                    StarLaunchMsec = starLaunchMsec,
                    StarArriveMsec = starArriveMsec,
                    UserNoteSize = 1f // SlideRoot的星星尺寸已经包含在localScale中
                };

                return noteInfo;
            }
            catch (Exception e)
            {
                MelonLogger.Warning($"Failed to get slide root star info: {e.Message}");
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
                    File.AppendAllText(_outputFilePath, "Format: Type-Index | PosX, PosY | LocalX, LocalY | Status | AppearMsec | IsEX | (Details...)\n");
                    File.AppendAllText(_outputFilePath, "  Touch: TouchDecor+Alpha(+TouchHoldProgress) | Hold: HoldScale+HoldSize | Tap/Break: TapScale\n");
                    File.AppendAllText(_outputFilePath, "  Star(1st): StarScale+UserNoteSize | Star-Move(2nd): StarScale+Alpha+LaunchMsec+ArriveMsec\n");
                    File.AppendAllText(_outputFilePath, "=".PadRight(30, '=') + "\n");

                    _isFileCreated = true;
                    MelonLogger.Msg($"Note dump output file: {_outputFilePath}");
                }

                // 构建数据行
                var lines = new List<string>();
                lines.Add($"Time:{currentTime:F4}|Count:{notes.Count}");

                foreach (var note in notes.OrderBy(n => n.NoteType).ThenBy(n => n.NoteIndex))
                {
                    // 基础信息
                    var line = $"{note.NoteType}-{note.NoteIndex} | " +
                               $"{note.Position.x:F4}, {note.Position.y:F4} | " +
                               $"{note.LocalPosition.x:F4}, {note.LocalPosition.y:F4} | " +
                               $"{note.Status} | {note.AppearMsec:F4} | " +
                               $"EX:{(note.IsExNote ? "Y" : "N")}";

                    var noteTypeLower = note.NoteType.ToLower();
                    
                    // Touch/Touch-Hold音符
                    if (noteTypeLower.Contains("touch"))
                    {
                        var decorPosition = note.TouchDecorPosition;
                        line += $" | TouchDecorPosition: {decorPosition.y:F4} | Alpha: {note.TouchAlpha:F4}";
                        if (note.NoteType == nameof(TouchHoldC))
                        {
                            line += $" | TouchHoldProgress: {note.TouchHoldProgress:F4}";
                        }
                    }
                    // Hold音符
                    else if (noteTypeLower.Contains("hold"))
                    {
                        line += $" | HoldScale: {note.HoldLocalScale.x:F4},{note.HoldLocalScale.y:F4} | HoldBodySize: {note.HoldBodySize.y:F4}";
                    }
                    // Star音符-Move（第二段）
                    else if (noteTypeLower.Contains("star") && note.IsSlideRootStar)
                    {
                        line += $" | StarScale: {note.StarLocalScale.x:F4},{note.StarLocalScale.y:F4}";
                        line += $" | Alpha: {note.StarAlpha:F4}";
                        line += $" | LaunchMsec: {note.StarLaunchMsec:F4} | ArriveMsec: {note.StarArriveMsec:F4}";
                    }
                    // Star音符（第一段）
                    else if (noteTypeLower.Contains("star"))
                    {
                        line += $" | StarScale: {note.StarLocalScale.x:F4},{note.StarLocalScale.y:F4} | UserNoteSize: {note.UserNoteSize:F4}";
                    }
                    // Tap音符
                    else if (noteTypeLower.Contains("tap") || noteTypeLower.Contains("break"))
                    {
                        line += $" | TapScale: {note.TapLocalScale.x:F4},{note.TapLocalScale.y:F4}";
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
