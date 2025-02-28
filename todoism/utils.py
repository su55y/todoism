import curses
import todoism.print as pr
import todoism.task as tsk


indent = 7
max_task_count = 99

def reid(task_list):
    """Reassign ids to every task in the list"""
    for i, t in enumerate(task_list):
        t['id'] = i + 1


def is_view_fully_packed(start, end, capacity):
    """indicates whether the current view is completely filled with tasks"""
    return end - start + 1 >= capacity


def move_by_word(text, current_pos, direction):
    """Move cursor by word in the specified direction
    
    Args:
        text: The text string to navigate
        current_pos: Current cursor position in the text
        direction: -1 for left, 1 for right
        
    Returns:
        New cursor position
    """
    if direction < 0:  # Left
        # If at beginning or first position, can't go left
        if current_pos <= 0:
            return 0
            
        # Skip spaces going left
        pos = current_pos - 1
        while pos > 0 and text[pos].isspace():
            pos -= 1
            
        # Find start of word
        while pos > 0 and not text[pos-1].isspace():
            pos -= 1
            
        return pos
    else:  # Right
        # If at or beyond end, can't go right
        if current_pos >= len(text):
            return len(text)
            
        # Skip current word
        pos = current_pos
        while pos < len(text) and not text[pos].isspace():
            pos += 1
            
        # Skip spaces
        while pos < len(text) and text[pos].isspace():
            pos += 1
            
        return pos

def render_edit_line(stdscr, task, y, scroll_offset, max_visible_width, cursor_pos_in_text=None, is_sidebar=False):
    """Helper function to render a task being edited with appropriate scrolling and styling"""
    return pr.render_task(
        stdscr=stdscr,
        task=task,
        y=y,
        is_selected=True,
        scroll_offset=scroll_offset,
        max_x=0,  # Let the function calculate this
        cursor_pos=cursor_pos_in_text,
        is_edit_mode=True,
        is_sidebar=is_sidebar  # Pass the sidebar flag
    )

def highlight_selection(stdscr, task, y, start_pos, end_pos, scroll_offset, is_sidebar=False):
    """Highlight selected text region"""
    # Highlight the selected region
    min_pos = min(start_pos, end_pos)
    max_pos = max(start_pos, end_pos)
    
    # Only highlight visible portion
    visible_start = max(min_pos, scroll_offset)
    visible_end = max_pos
    
    # Apply highlighting to each visible character
    for i in range(visible_start, visible_end):
        # Calculate screen position based on whether we're in sidebar or task area
        if is_sidebar:
            screen_pos = 3 + (i - scroll_offset)  # 3 is position after ID in sidebar
        else:
            screen_pos = indent + 16 + (i - scroll_offset)  # Task position with sidebar offset
            
        if i - scroll_offset >= 0:  # Ensure we only render visible chars
            try:
                stdscr.addstr(y, screen_pos, task['description'][i], curses.A_REVERSE)
            except curses.error:
                # Skip characters that would go past the edge of the screen
                pass

def edit(stdscr, task, mode, initial_scroll=0, initial_cursor_pos=None, is_sidebar=False):
    """
    A editing wrapper implemented using getch(). It delivers 
    more comprehensive functionalities than getstr() does.
    """
    # Standardize indent calculations
    if is_sidebar:
        # For sidebar, text starts at position 1 (1-space indent from left)
        sidebar_width = 0  # No offset needed when editing sidebar items
        base_indent = 1    # 1 space indent from left edge
        text_start_pos = base_indent  # Start with consistent 1-space indent
    else:
        # For tasks, use the standard sidebar offset
        sidebar_width = 16  # 15 chars + 1 for separator
        base_indent = 7    # Length of ID + status + flag area
        text_start_pos = sidebar_width + base_indent  # Combined offset for text start
    
    # Selection state variables
    selection_active = False
    selection_start = -1
    debug_keys = False
    scroll_offset = initial_scroll
    MAX_DESCRIPTION_LENGTH = 500
    
    # Initialize cursor position
    if initial_cursor_pos is not None:
        cursor_pos_in_text = min(initial_cursor_pos, len(task['description']))
    else:
        cursor_pos_in_text = len(task['description'])  # Start at end of text for new tasks
    
    max_y, max_x = stdscr.getmaxyx()
    
    # Calculate available width
    if is_sidebar:
        # For sidebar, limit width to sidebar width (15) minus the starting position
        date_length = 0  # No date shown in sidebar
        date_pos = 15  # End at sidebar width
        max_visible_width = date_pos - base_indent  # Usually around 12 characters visible
    else:
        # For tasks, calculate based on date position
        date_length = len(task['date'])
        date_pos = max_x - date_length - 1
        max_visible_width = date_pos - text_start_pos - 1
    
    original_text = task['description']
    y = stdscr.getyx()[0]
    
    # Initial render with proper offset
    target_x = render_edit_line(stdscr, task, y, scroll_offset, max_visible_width, cursor_pos_in_text, is_sidebar)
    stdscr.move(y, target_x)
    stdscr.refresh()
    
    lock_scrolling = True 
    stabilize_count = 3
    
    while True:
        # Get current position
        y, x = stdscr.getyx()
        max_y, max_x = stdscr.getmaxyx()
        
        # Clear the edit line WITHOUT clearing the category at the same height
        if is_sidebar:
            # For sidebar editing, clear just the sidebar area
            stdscr.move(y, 0)
            # Don't use clrtoeol() - it clears the entire line including task area
            # Instead, clear character by character only in sidebar area
            for j in range(15):  # Columns 0-14 (sidebar area)
                stdscr.addch(y, j, ' ')
            stdscr.refresh()
            # Restore the separator after clearing
            stdscr.addch(y, 15, '│')
            stdscr.refresh()
            # No ID redrawing - we're not displaying IDs anymore
        else:
            # Only clear from the separator onwards, preserving sidebar content
            sidebar_width = 16  # Always use 16 here to preserve sidebar content
            
            # Move to the separator and clear only to the right
            stdscr.move(y, 16)  # Position just after separator
            stdscr.clrtoeol()
            
            # Redraw vertical separator (critical fix)
            stdscr.addstr(y, 15, "│")
            
            # Redraw task ID
            stdscr.addstr(y, sidebar_width, f"{task['id']:2d} ")
            
            # Task symbol area needs redrawing too
            if 'status' in task or 'flagged' in task:
                import todoism.print as pr
                pr.print_task_symbols(
                    stdscr, 
                    task, 
                    y, 
                    sidebar_width + 3, 
                    sidebar_width + 5, 
                    True, 
                    True
                )
        
        # Recalculate with current screen dimensions
        if is_sidebar:
            date_pos = 15  # End of sidebar area
            max_visible_width = date_pos - base_indent
        else:
            date_pos = max_x - date_length - 1
            max_visible_width = date_pos - text_start_pos - 1
            
        right_limit = date_pos - 1
        
        # Calculate cursor position in text
        cursor_pos_in_text = x - text_start_pos + scroll_offset
        
        # Check if text has changed
        text_modified = task['description'] != original_text
        
        # Render the edit line with current scroll offset
        target_x = render_edit_line(stdscr, task, y, scroll_offset, max_visible_width, cursor_pos_in_text, is_sidebar)
        
        # Add selection highlighting if active
        if selection_active:
            highlight_selection(stdscr, task, y, selection_start, cursor_pos_in_text, scroll_offset, is_sidebar)
        
        # Position cursor
        stdscr.move(y, target_x)
        
        # Get user input
        ch = stdscr.getch()
        
        # Debug mode - display current key code in top-left corner
        if debug_keys:
            debug_info = f"Key: {ch} | Pos: {cursor_pos_in_text}/{len(task['description'])} | Scroll: {scroll_offset}"
            # Save current cursor position
            current_y, current_x = stdscr.getyx()
            # Clear the debug area
            stdscr.addstr(0, 0, " " * min(len(debug_info) + 5, max_x))
            # Display debug info
            stdscr.attron(curses.color_pair(4))  # Red color for visibility
            stdscr.addstr(0, 0, debug_info)
            stdscr.attroff(curses.color_pair(4))
            # Restore cursor position
            stdscr.move(current_y, current_x)
        
        # Only decrement stabilize_count on actual keystrokes (not for -1 or timeout)
        if ch != -1 and stabilize_count > 0:
            stabilize_count -= 1
            # Only unlock scrolling after stabilize period
            if stabilize_count == 0:
                lock_scrolling = False
        
        # REMOVED: No more automatic scrolling logic here
        
        # Handle key presses
        if ch == 4:  # Toggle debug mode with Ctrl+D
            debug_keys = not debug_keys
            # Clear debug area when turning off
            if not debug_keys:
                current_y, current_x = stdscr.getyx()
                stdscr.addstr(0, 0, " " * max_x)
                stdscr.move(current_y, current_x)
            continue
        elif ch == 10:  # Enter to complete
            break
        elif ch == 27:  # ESC
            if mode == pr.add_mode:
                return ""
            else:
                # Clear selection if active
                selection_active = False
                selection_start = -1
                continue
                
        elif ch == curses.KEY_LEFT:
            # Clear selection if active
            if selection_active:
                selection_active = False
                selection_start = -1
            
            # Only move if not already at the beginning of text
            if cursor_pos_in_text > 0:
                # Calculate new position in text
                new_pos_in_text = cursor_pos_in_text - 1
                
                # Calculate new screen position
                new_x = text_start_pos + (new_pos_in_text - scroll_offset)
                # If cursor would move off-screen left, adjust scroll
                if new_pos_in_text < scroll_offset:
                    scroll_offset = max(0, new_pos_in_text)
                    new_x = text_start_pos
                stdscr.move(y, new_x)
            else:
                # Already at beginning of text
                stdscr.move(y, text_start_pos)
                
        elif ch == curses.KEY_RIGHT:
            # Clear selection if active
            if selection_active:
                selection_active = False
                selection_start = -1
                
            # Don't move if already at the absolute end of the text
            if cursor_pos_in_text >= len(task['description']):
                # This is critical - reset cursor to end position but don't change scroll
                new_x = text_start_pos + (len(task['description']) - scroll_offset)
                new_x = min(new_x, right_limit)
                stdscr.move(y, new_x)
                continue
                
            # Move right but strictly check against text length
            new_pos = cursor_pos_in_text + 1
            # Hard limit to prevent going past text end
            new_pos = min(new_pos, len(task['description']))
                
            # Calculate screen position
            new_x = text_start_pos + (new_pos - scroll_offset)
            
            # Only scroll if cursor would move out of view
            if new_x > right_limit:
                # Only scroll the minimum needed to show cursor
                scroll_amount = new_x - right_limit
                scroll_offset += scroll_amount
                new_x = right_limit
            
            stdscr.move(y, new_x)
        
        # Ctrl+Left to move to previous word (without selection)
        elif ch == 554:
            if cursor_pos_in_text <= 0:
                continue
                
            # Clear selection if active
            if selection_active:
                selection_active = False
                selection_start = -1
                
            # Find the start of the previous word
            new_pos = move_by_word(task['description'], cursor_pos_in_text, -1)
            
            # KEY FIX: Check if we're near the end of text (within 5 chars)
            near_end = len(task['description']) - cursor_pos_in_text <= 5
            
            # Only adjust scroll if we're not near the end
            if not near_end and new_pos < scroll_offset + 5:
                scroll_offset = max(0, new_pos - 5)
            elif near_end and new_pos < scroll_offset:
                # If near end but would go out of view, make minimal adjustment
                scroll_offset = new_pos
            
            # Calculate new safe screen position
            new_x = text_start_pos + (new_pos - scroll_offset)
            # Use right_limit instead of hardcoded max_x - 23
            new_x = min(new_x, right_limit)
            
            stdscr.move(y, new_x)
         
        # Ctrl+Right to move to next word (without selection)
        elif ch == 569:
            # Don't do anything if already at the end of text
            if cursor_pos_in_text >= len(task['description']):
                # KEY FIX: Explicitly stabilize position at the end
                new_x = text_start_pos + (len(task['description']) - scroll_offset)
                new_x = min(new_x, date_pos - 1)  # Ensure we respect the gap
                stdscr.move(y, new_x)
                continue
                
            # Find the end of the next word
            new_pos = move_by_word(task['description'], cursor_pos_in_text, 1)
            
            # Only adjust scroll if necessary AND we're not at the end
            if new_pos < len(task['description']) and new_pos > scroll_offset + max_visible_width - 5:
                # Limited scroll adjustment to prevent large jumps
                scroll_offset = min(
                    new_pos - max_visible_width + 5,
                    len(task['description']) - max_visible_width  # Don't scroll past end
                )
                # Ensure scroll_offset is never negative
                scroll_offset = max(0, scroll_offset)
            
            # Calculate new safe screen position
            new_x = text_start_pos + (new_pos - scroll_offset)
            # Use date_pos instead of hardcoded max_x - 23
            new_x = min(new_x, date_pos - 1)
            
            stdscr.move(y, new_x)
            
        # Try multiple common key code patterns for Ctrl+Shift+Left
        elif ch in [545, 547, 443, 541, 71, 555]:
            if cursor_pos_in_text <= 0:
                continue
                
            if not selection_active:
                selection_active = True
                selection_start = cursor_pos_in_text
                
            # Find the start of the previous word
            new_pos = move_by_word(task['description'], cursor_pos_in_text, -1)
            
            # Adjust scroll if needed
            if new_pos < scroll_offset + 5:
                scroll_offset = max(0, new_pos - 5)
            
            # Calculate new safe screen position
            new_x = text_start_pos + (new_pos - scroll_offset)
            if new_x >= max_x - 23:
                new_x = max_x - 23
            
            stdscr.move(y, new_x)
            
        # Try multiple common key code patterns for Ctrl+Shift+Right
        elif ch in [560, 562, 444, 556, 86, 570]:
            if cursor_pos_in_text >= len(task['description']):
                continue
                
            if not selection_active:
                selection_active = True
                selection_start = cursor_pos_in_text
                
            # Find the end of the next word
            new_pos = move_by_word(task['description'], cursor_pos_in_text, 1)
            
            # Adjust scroll if needed
            if new_pos > scroll_offset + max_visible_width - 5:
                scroll_offset = new_pos - max_visible_width + 5
            
            # Calculate new safe screen position
            new_x = text_start_pos + (new_pos - scroll_offset)
            if new_x >= max_x - 23:
                new_x = max_x - 23
            
            stdscr.move(y, new_x)
            
        # Try multiple common key code patterns for Ctrl+Shift+Backspace or Ctrl+W
        elif ch in [523, 527, 23, 127]:
            if cursor_pos_in_text <= 0:
                continue
                
            # Find the start of the previous word
            new_pos = move_by_word(task['description'], cursor_pos_in_text, -1)
            
            # Delete characters from new position to current position
            task['description'] = task['description'][:new_pos] + task['description'][cursor_pos_in_text:]
            
            # Adjust scroll if needed
            if new_pos < scroll_offset + 5:
                scroll_offset = max(0, new_pos - 5)
            
            # Calculate new safe screen position
            new_x = text_start_pos + (new_pos - scroll_offset)
            if new_x >= max_x - 23:
                new_x = max_x - 23
            
            # Clear selection state
            selection_active = False
            selection_start = -1
            
            stdscr.move(y, new_x)
            
        # Try multiple common key code patterns for Ctrl+Shift+Delete or Ctrl+Alt+D
        elif ch in [524, 528, 127, 4]:
            if cursor_pos_in_text >= len(task['description']):
                continue
                
            # Find the end of the next word
            new_pos = move_by_word(task['description'], cursor_pos_in_text, 1)
            
            # Delete characters from current position to new position
            task['description'] = task['description'][:cursor_pos_in_text] + task['description'][new_pos:]
            
            # Clear selection state
            selection_active = False
            selection_start = -1
            
        elif ch == curses.KEY_BACKSPACE or ch == 127:  # Backspace
            # Clear selection if active
            if selection_active:
                # Delete the selected text
                min_pos = min(selection_start, cursor_pos_in_text)
                max_pos = max(selection_start, cursor_pos_in_text)
                
                # Fixed concatenation - properly join text before min_pos with text after max_pos
                task['description'] = task['description'][:min_pos] + task['description'][max_pos:]
                
                selection_active = False
                selection_start = -1
                
                # Adjust scroll if needed
                if min_pos < scroll_offset + 5:
                    scroll_offset = max(0, min_pos - 5)
                
                # Position cursor at deletion point
                new_x = text_start_pos + (min_pos - scroll_offset)
                new_x = min(new_x, right_limit)  # Use right_limit instead of hardcoded value
                
                stdscr.move(y, new_x)
                continue
            
            # Can't backspace past the start
            if x <= text_start_pos:
                stdscr.move(y, text_start_pos)
                continue
            
            # CRITICAL FIX: Save the text length before deletion
            old_length = len(task['description'])
            
            # Verify cursor position is valid before deletion
            if cursor_pos_in_text <= 0 or cursor_pos_in_text > old_length:
                # Invalid position - do nothing
                continue
            
            # Delete character before cursor - properly sliced
            task['description'] = task['description'][:cursor_pos_in_text - 1] + task['description'][cursor_pos_in_text:]
            
            # Calculate new cursor position in text
            new_cursor_pos = cursor_pos_in_text - 1
            
            # Special handling for deletion at end of text
            at_end = cursor_pos_in_text >= old_length
            
            # Adjust scroll if needed
            if at_end and scroll_offset > 0:
                # When deleting from end of text, adjust scroll to keep visible area stable
                scroll_offset = max(0, scroll_offset - 1)
            elif new_cursor_pos < scroll_offset + 5 and scroll_offset > 0:
                # Standard adjustment for deleting near left edge of view
                scroll_offset = max(0, new_cursor_pos - 5)
            
            # Calculate correct screen position after deletion
            new_x = text_start_pos + (new_cursor_pos - scroll_offset)
            
            # Ensure position is valid
            new_x = max(text_start_pos, min(new_x, right_limit))
            
            stdscr.move(y, new_x)
        
        elif 32 <= ch < 127:  # Printable char
            # Check maximum length
            if len(task['description']) >= MAX_DESCRIPTION_LENGTH and not selection_active:
                continue
                
            # If a selection is active, replace it with the typed character
            if selection_active:
                # ... existing selection handling code ...
                continue
                
            # FIXED: Ensure cursor position is valid before insertion
            if cursor_pos_in_text < 0 or cursor_pos_in_text > len(task['description']):
                cursor_pos_in_text = min(max(0, cursor_pos_in_text), len(task['description']))
            
            # Keep track of whether we're at the end of text before insertion
            at_end_of_text = cursor_pos_in_text == len(task['description'])
            
            # CRITICAL FIX: Record length before insertion to detect pastes
            original_length = len(task['description'])
            
            # Insert character at the correct position
            task['description'] = task['description'][:cursor_pos_in_text] + chr(ch) + task['description'][cursor_pos_in_text:]
            
            # Calculate new cursor position in text
            new_cursor_pos = cursor_pos_in_text + 1
            
            at_end_of_text = cursor_pos_in_text == len(task['description'])
            
            # FIX: Recalculate screen boundaries with exactly 1 space gap
            date_length = len(task['date'])
            date_pos = max_x - date_length - 1  # Position where date starts (with 1 char gap)
            max_visible_width = date_pos - (text_start_pos)  # Total spaces available for text
            right_limit = date_pos - 1  # Position of the 1 char gap
            
            # COMPLETELY REVISED LOGIC FOR END OF TEXT INSERTION
            if at_end_of_text:
                # When we're at the end of text and need to scroll:
                if new_cursor_pos > scroll_offset + max_visible_width:
                    # First update the scroll position before updating cursor
                    scroll_offset = new_cursor_pos - max_visible_width
                
                # Always update cursor position after any scroll adjustment
                cursor_pos_in_text = new_cursor_pos
            elif cursor_pos_in_text - scroll_offset >= max_visible_width - 1:
                # When cursor is at the edge of visible area but not at end of text
                # We need to scroll by 1 to show the newly inserted character
                scroll_offset += 1
                cursor_pos_in_text = new_cursor_pos
            else:
                # Regular case - just update cursor position
                cursor_pos_in_text = new_cursor_pos
            
            # Calculate new cursor X position with consistent gap
            new_x = text_start_pos + (new_cursor_pos - scroll_offset)
            
            # Safety check to ensure we never go beyond right_limit
            new_x = min(new_x, right_limit)
            
            stdscr.move(y, new_x)
        
        # Alt+Left to jump to beginning of text (handle various terminal key codes)
        elif ch in [537, 543, 27, 542, 451, 552]:  # Various codes for Alt+Left
            # If ESC (27), need to check if it's followed by proper sequence
            if ch == 27:
                # Check for ESC sequence
                next_ch = stdscr.getch()
                if next_ch != ord('[') and next_ch != 91:  # Check for '[' character
                    continue
                    
                direction_ch = stdscr.getch()
                if direction_ch != 49 and direction_ch != ord('1'):  # Not part of Alt+Left sequence
                    continue
                    
                final_ch = stdscr.getch()
                if final_ch != 59 and final_ch != ord(';'):  # Not part of Alt+Left sequence
                    continue
                    
                mod_ch = stdscr.getch()
                if mod_ch != 51 and mod_ch != ord('3'):  # Not Alt modifier (3)
                    continue
                    
                arrow_ch = stdscr.getch()
                if arrow_ch != 68 and arrow_ch != ord('D'):  # Not left arrow ('D')
                    continue
            
            # Clear selection if active
            if selection_active:
                selection_active = False
                selection_start = -1
                
            # Jump to beginning of text
            cursor_pos_in_text = 0
            
            # Reset scroll offset to show beginning of text
            scroll_offset = 0
            
            # Position cursor at beginning
            stdscr.move(y, text_start_pos)
            
        # Alt+Right to jump to end of text (handle various terminal key codes)
        elif ch in [552, 558, 402, 500, 567]:  # Various codes for Alt+Right
            # If ESC (27), need to check if it's followed by proper sequence
            if ch == 27:
                # Check for ESC sequence
                next_ch = stdscr.getch()
                if next_ch != ord('[') and next_ch != 91:  # Check for '[' character
                    continue
                    
                direction_ch = stdscr.getch()
                if direction_ch != 49 and direction_ch != ord('1'):  # Not part of Alt+Right sequence
                    continue
                    
                final_ch = stdscr.getch()
                if final_ch != 59 and final_ch != ord(';'):  # Not part of Alt+Right sequence
                    continue
                    
                mod_ch = stdscr.getch()
                if mod_ch != 51 and mod_ch != ord('3'):  # Not Alt modifier (3)
                    continue
                    
                arrow_ch = stdscr.getch()
                if arrow_ch != 67 and arrow_ch != ord('C'):  # Not right arrow ('C')
                    continue
            
            # Clear selection if active
            if selection_active:
                selection_active = False
                selection_start = -1
                
            # Jump to end of text
            cursor_pos_in_text = len(task['description'])
            
            # For long text, adjust scroll to show the end of text
            if len(task['description']) > max_visible_width:
                # Calculate scroll needed to position cursor at right side with proper buffer
                scroll_offset = max(0, len(task['description']) - max_visible_width)
                
                # Position cursor at end with proper right side alignment
                new_x = text_start_pos + max_visible_width
                new_x = min(new_x, right_limit)
            else:
                # For short text, no scroll needed
                scroll_offset = 0
                new_x = text_start_pos + len(task['description'])
                
            # Ensure we respect the right boundary
            new_x = min(new_x, right_limit)
            stdscr.move(y, new_x)
            
    return task['description']

def edit_and_save(stdscr, task_list, id, row, start, end, y, x, max_capacity):
    """Edit task with improved cursor positioning and scrolling behavior"""
    # Get screen dimensions
    max_y, max_x = stdscr.getmaxyx()
    
    # Get description length
    description_length = len(task_list[id - 1]['description'])
    date_length = len(task_list[id - 1]['date'])
    
    # Calculate exact space available for text (accounting for date + gap)
    date_pos = max_x - date_length - 1  # -1 for exactly one character gap before date
    available_width = date_pos - (indent + 16) - 1  # -1 ensures the gap is preserved
    
    # NEW BEHAVIOR: Always initialize with scroll_offset = 0 to show beginning of text
    scroll_offset = 0
    
    # Position cursor differently based on text length:
    if description_length <= available_width:
        # For short tasks (text fits): position at end of text
        cursor_x = indent + 16 + description_length
    else:
        # For long tasks: position at end of visible portion
        cursor_x = indent + 16 + available_width
    
    # Make sure cursor position is within screen bounds
    cursor_x = min(cursor_x, date_pos - 1)  # Ensure exactly one char gap
    
    # Calculate cursor position in text
    cursor_pos_in_text = cursor_x - (indent + 16) + scroll_offset
    
    # Render once with fixed parameters before entering edit mode
    render_edit_line(stdscr, task_list[id - 1], y, scroll_offset, available_width, cursor_pos_in_text)
    
    # Set cursor at the calculated position
    stdscr.move(y, cursor_x)
    
    # Initialize the edit function with the appropriate scroll offset and cursor position
    task_list[id - 1]['description'] = edit(
        stdscr, 
        task_list[id - 1], 
        pr.edit_mode, 
        initial_scroll=scroll_offset,
        initial_cursor_pos=cursor_pos_in_text
    )
    
    # Handle task deletion if description is empty
    if task_list[id - 1]['description'] == "":
        del task_list[id - 1]
        reid(task_list)
        id, row, start, end = post_deletion_update(id, row, start, end, len(task_list) + 1, max_capacity)
    
    # Save changes
    tsk.save_tasks(task_list, tsk.tasks_file_path)
    return id, row, start, end

def post_deletion_update(current_id, current_row, start, end, prev_task_cnt, max_capacity):
    """
    Update the current view after deletion: 
    1. 2x Backspaces
    2. edit to empty 
    3. command del
    
    There are 4 senarios where the view is fully packed with tasks before deletion:
    
                                       │       │                                       │       │
    Senario 1: ┌───────┐    Senario 2: ├───────┤    Senario 3: ┌───────┐    Senario 4: ├───────┤
               ├───────┤               ├───────┤               ├───────┤               ├───────┤
               ├───────┤               ├───────┤               ├───────┤               ├───────┤   
               ├───────┤               ├───────┤               └───────┘               ├───────┤                  
               └───────┘               └───────┘                                       │       │
                                                               │       │               │       │
    And the view update rules are similar to the Apple Reminder's
                
                
    There is only 1 senario where the view is not fully packed with tasks:
    
    Senario 5: ┌───────┐
               ├───────┤
               ├───────┤
               │       │
               └───────┘
    """
    if is_view_fully_packed(start, end, max_capacity):
        # Senarios 1
        if prev_task_cnt == max_capacity:
            # delete the last task, otherwise the row and id both remains unchanged
            if current_id == end:
                current_row = current_row - 1
                current_id = current_id - 1
            end = end - 1
        # Senario 2
        elif prev_task_cnt == end and prev_task_cnt > max_capacity:
            start = start - 1
            end = end - 1
            current_id = current_id - 1
        # Senario 3 and 4 does not lead to any change
    
    # Senario 5
    else:
        end = end - 1
        if current_id == prev_task_cnt:
            current_row = current_row - 1
            current_id = current_id - 1
    return current_id, current_row, start, end