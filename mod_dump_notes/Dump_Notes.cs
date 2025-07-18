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
                            // 只处理 Tap 和 Hold 音符
                            string noteType = GetNoteTypeName(note);
                            if (noteType == "Tap" || noteType == "Hold")
                            {
                                var noteInfo = GetNoteInfo(note, noteType);
                                if (noteInfo != null)
                                    allNotes.Add(noteInfo);
                            }
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
                    AppearMsec = -1f  // 默认值
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

        private static string GetNoteTypeName(NoteBase noteBase)
        {
            string typeName = noteBase.GetType().Name;

            // 简化类型名称，只识别 Tap 和 Hold
            if (typeName.Contains("Tap") && !typeName.Contains("Hold")) return "Tap";
            if (typeName.Contains("Hold")) return "Hold";

            return "Other";  // 其他类型暂时不处理
        }

        private static void PrintNoteFrame(float currentTime, List<NoteInfo> notes)
        {
            try
            {
                // 设置输出文件路径（第一帧时）
                if (!_isFileCreated)
                {
                    var desktopPath = @"C:\Users\ck273\Desktop";
                    _outputFilePath = Path.Combine(desktopPath, $"{DateTime.Now:yyyy-MM-dd_HH-mm-ss}.txt");

                    // 创建文件并写入头部信息
                    File.WriteAllText(_outputFilePath, $"Note Dump Started at {DateTime.Now:yyyy-MM-dd HH:mm:ss}\n");
                    File.AppendAllText(_outputFilePath, "Format: Time|Type|Index|PosX|PosY|LocalX|LocalY|Status|AppearMsec\n");
                    File.AppendAllText(_outputFilePath, "=".PadRight(100, '=') + "\n");

                    _isFileCreated = true;
                    MelonLogger.Msg($"Note dump output file: {_outputFilePath}");
                }

                // 构建数据行
                var lines = new List<string>();
                lines.Add($"Frame:{currentTime:F2}|Count:{notes.Count}");

                foreach (var note in notes.OrderBy(n => n.NoteType).ThenBy(n => n.NoteIndex))
                {
                    var line = $"{currentTime:F2}|{note.NoteType}|{note.NoteIndex}|" +
                            $"{note.Position.x:F2}|{note.Position.y:F2}|" +
                            $"{note.LocalPosition.x:F2}|{note.LocalPosition.y:F2}|" +
                            $"{note.Status}|{note.AppearMsec:F1}";
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
