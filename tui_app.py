import os
import sys
import re
from typing import Optional
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, DirectoryTree, TextArea, Markdown, Input, Tabs, Tab
from textual.widgets.text_area import Selection
from textual.binding import Binding
from textual.reactive import reactive

class CustomDirectoryTree(DirectoryTree):
                                                           
    ICON_FILE = "  "
    ICON_NODE = "+ "
    ICON_NODE_EXPANDED = "- "

class TuiEditorApp(App):
    CSS_PATH = "tui_app.css"
    
    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Файлы", show=True),
        Binding("ctrl+l", "focus_sidebar", "Сайдбар", show=True),
        Binding("ctrl+e", "focus_editor", "Редактор", show=True),
        Binding("ctrl+p", "toggle_preview", "Превью (разметка)", show=True),
        Binding("ctrl+f", "toggle_search", "Поиск", show=True),
        Binding("ctrl+s", "save_file", "Сохранить", show=True),
        Binding("ctrl+w", "close_file", "Закрыть", show=True),
        Binding("ctrl+q", "quit", "Выход", show=True),
        Binding("shift+left", "focus_sidebar", "Файлы (Shift+Left)", show=False),
        Binding("shift+right", "focus_editor", "Редактор (Shift+Right)", show=False),
    ]
    
    current_file_path: reactive[Optional[Path]] = reactive(None)
    is_modified: reactive[bool] = reactive(False)
    
                                      
    open_files: list[Path] = []
    
                                                                    
    tab_rebuild_counter: int = 0
    
                      
    search_matches: list[int] = []
    current_match_idx: int = -1

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
                                   
            yield CustomDirectoryTree(
                path=str(Path.cwd()),
                id="sidebar"
            )
                                                
            with Vertical(id="editor-container"):
                yield Tabs(id="tabs-bar")
                yield Input(
                    placeholder="Поиск (введите текст, Enter — далее, Esc — закрыть)...",
                    id="search-input"
                )
                yield TextArea(
                    id="editor",
                    show_line_numbers=True,
                )
                yield Markdown(
                    id="preview"
                )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "KrutoiEditor"
        self.sub_title = "Новый файл"
        
                                  
        editor = self.query_one("#editor", TextArea)
        editor.theme = "dracula"                              
        editor.language = "markdown"
        
                                                                         
        if len(sys.argv) > 1:
            file_to_open = Path(sys.argv[1]).resolve()
            self.open_file(file_to_open)

    def watch_current_file_path(self, path: Optional[Path]) -> None:
        if path:
            self.title = f"KrutoiEditor - {path.name}"
            self.sub_title = str(path.parent)
        else:
            self.title = "KrutoiEditor"
            self.sub_title = "Новый файл"

    def watch_is_modified(self, modified: bool) -> None:
        if modified:
            self.title = f"* {self.title.lstrip('* ')}"
        else:
            if self.title.startswith("* "):
                self.title = self.title[2:]

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        self.open_file(Path(event.path))

    def open_file(self, path: Path, update_tabs: bool = True) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            editor = self.query_one("#editor", TextArea)
            preview = self.query_one("#preview", Markdown)
            
            preview.display = False
            editor.display = True
            
                                                                          
            self.is_modified = False
            editor.text = content
            editor.theme = "dracula"                                  
            self.current_file_path = path
            
                                                                                 
            if path.suffix == ".md":
                editor.language = "markdown"
                self.update_preview(content)
            elif path.suffix == ".py":
                editor.language = "python"
                self.update_preview(f"# Python File: {path.name}\n\n*Предпросмотр markdown недоступен для Python-файлов.*")
            else:
                editor.language = "markdown"                             
                self.update_preview(content)
                
            if update_tabs:
                tabs = self.query_one("#tabs-bar", Tabs)
                if path not in self.open_files:
                    self.open_files.append(path)
                
                                                                                             
                self.tab_rebuild_counter += 1
                tabs.clear()
                for idx, p in enumerate(self.open_files):
                    tabs.add_tab(Tab(p.name, id=f"tab_{idx}_{self.tab_rebuild_counter}"))
                
                                                                        
                self._updating_tab_active = True
                active_idx = self.open_files.index(path)
                tabs.active = f"tab_{active_idx}_{self.tab_rebuild_counter}"
                self._updating_tab_active = False
                
            self.notify(f"Файл успешно открыт: {path.name}", severity="information")
            
                                                                                                              
            self.set_timer(0.05, editor.focus)
            
        except Exception as e:
            self.notify(f"Ошибка чтения файла: {str(e)}", severity="error")

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        \
        if getattr(self, "_updating_tab_active", False):
            return
        if event.tab and event.tab.id and event.tab.id.startswith("tab_"):
            try:
                parts = event.tab.id.split("_")
                idx = int(parts[1])
                counter = int(parts[2])
                                                                             
                if counter == self.tab_rebuild_counter:
                    path = self.open_files[idx]
                    if self.current_file_path != path:
                        self.open_file(path, update_tabs=False)
            except (IndexError, ValueError):
                pass

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self.is_modified = True
        editor = self.query_one("#editor", TextArea)
        if self.current_file_path and self.current_file_path.suffix == ".md":
            self.update_preview(editor.text)
        elif not self.current_file_path:
            self.update_preview(editor.text)

    def update_preview(self, text: str) -> None:
        preview = self.query_one("#preview", Markdown)
        if preview.display:
            try:
                preview.update(text)
            except Exception:
                pass

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display
        if sidebar.display:
            sidebar.focus()
        else:
            self.focus_active_widget()

    def focus_active_widget(self) -> None:
        editor = self.query_one("#editor")
        preview = self.query_one("#preview")
        if preview.display:
            preview.focus()
        else:
            editor.focus()

    def action_focus_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        if sidebar.display:
            sidebar.focus()

    def action_focus_editor(self) -> None:
        editor = self.query_one("#editor")
        preview = self.query_one("#preview")
        if preview.display:
            preview.display = False
            editor.display = True
        editor.focus()

    def action_toggle_preview(self) -> None:
        editor = self.query_one("#editor", TextArea)
        preview = self.query_one("#preview", Markdown)
        
        if preview.display:
                                   
            current_scroll_ratio = 0
            if getattr(preview, "max_scroll_y", 0) > 0:
                current_scroll_ratio = preview.scroll_y / preview.max_scroll_y
                
            preview.display = False
            editor.display = True
            
            if getattr(editor, "max_scroll_y", 0) > 0:
                editor.scroll_y = int(current_scroll_ratio * editor.max_scroll_y)
                
            editor.focus()
        else:
                               
            current_scroll_ratio = 0
            if getattr(editor, "max_scroll_y", 0) > 0:
                current_scroll_ratio = editor.scroll_y / editor.max_scroll_y
                
            self.update_preview(editor.text)
            editor.display = False
            preview.display = True
            
            if getattr(preview, "max_scroll_y", 0) > 0:
                                                                       
                self.set_timer(0.05, lambda: setattr(preview, "scroll_y", int(current_scroll_ratio * preview.max_scroll_y)))
                
            preview.focus()

    def action_toggle_search(self) -> None:
        search_input = self.query_one("#search-input", Input)
        search_input.display = not search_input.display
        if search_input.display:
            search_input.focus()
        else:
            self.focus_active_widget()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.perform_search(event.value, find_next=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.perform_search(event.value, find_next=True)

    def on_key(self, event) -> None:
                                                                   
        if event.key == "escape":
            search_input = self.query_one("#search-input", Input)
            if search_input.display:
                search_input.display = False
                self.focus_active_widget()
                event.prevent_default()
                event.stop()

    def perform_search(self, query: str, find_next: bool = False) -> None:
        if not query:
            self.search_matches = []
            self.current_match_idx = -1
            return

        editor = self.query_one("#editor", TextArea)
        text = editor.text
        
                                                    
        matches = [m.start() for m in re.finditer(re.escape(query), text, re.IGNORECASE)]
        
        if not matches:
            self.search_matches = []
            self.current_match_idx = -1
            return
        
        self.search_matches = matches
        
        if find_next:
            self.current_match_idx = (self.current_match_idx + 1) % len(matches)
        else:
            self.current_match_idx = 0
            
        offset = matches[self.current_match_idx]
        row, col = self.offset_to_location(text, offset)
        
        editor.move_cursor((row, col))
        editor.selection = Selection((row, col), (row, col + len(query)))

    def offset_to_location(self, text: str, offset: int) -> tuple[int, int]:
        lines = text[:offset].split('\n')
        row = len(lines) - 1
        col = len(lines[-1]) if lines else 0
        return (row, col)

    def action_close_file(self) -> None:
        \
        if not self.current_file_path:
            return
        
        path_to_remove = self.current_file_path
        if path_to_remove in self.open_files:
            self.open_files.remove(path_to_remove)
            
        tabs = self.query_one("#tabs-bar", Tabs)
        
        self.tab_rebuild_counter += 1
        tabs.clear()
        
        if self.open_files:
            for idx, p in enumerate(self.open_files):
                tabs.add_tab(Tab(p.name, id=f"tab_{idx}_{self.tab_rebuild_counter}"))
                                                   
            self.open_file(self.open_files[0])
        else:
                                        
            self.current_file_path = None
            editor = self.query_one("#editor", TextArea)
            editor.text = ""
            self.is_modified = False
            self.update_preview("")
            self.notify("Все вкладки закрыты", severity="information")

    def action_save_file(self) -> None:
        editor = self.query_one("#editor", TextArea)
        if self.current_file_path:
            self.save_to_path(self.current_file_path, editor.text)
        else:
                                                                        
            default_path = Path.cwd() / "untitled.md"
            self.save_to_path(default_path, editor.text)
            self.current_file_path = default_path
            
                                                                  
            try:
                self.query_one("#sidebar", CustomDirectoryTree).reload()
            except Exception:
                pass

    def save_to_path(self, path: Path, content: str) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.is_modified = False
            
                                                                 
            tabs = self.query_one("#tabs-bar", Tabs)
            if path not in self.open_files:
                self.open_files.append(path)
                
            self.tab_rebuild_counter += 1
            tabs.clear()
            for idx, p in enumerate(self.open_files):
                tabs.add_tab(Tab(p.name, id=f"tab_{idx}_{self.tab_rebuild_counter}"))
            
            self._updating_tab_active = True
            active_idx = self.open_files.index(path)
            tabs.active = f"tab_{active_idx}_{self.tab_rebuild_counter}"
            self._updating_tab_active = False

            self.notify(f"Файл сохранен: {path.name}", severity="information")
        except Exception as e:
            self.notify(f"Ошибка сохранения: {str(e)}", severity="error")

if __name__ == "__main__":
    app = TuiEditorApp()
    app.run()
