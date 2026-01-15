# Editable Sample Questions Feature

## Feature Overview

Added collaborative, editable sample questions documentation accessible directly in the Chainlit UI.

---

## What Was Implemented

### 1. **Sample Questions File**
- **Location**: `sample_questions.md`
- **Content**: Pre-populated with 12 categories of research-based sample questions
- **Format**: Markdown with examples using the `|` separator pattern
- **Editable**: Team can modify, add, or remove questions

### 2. **New Commands**

#### `/samples` - View Sample Questions
```
/samples
```
- Displays the current sample questions
- Formatted markdown rendering
- Shows all categories and examples
- Includes quick reference for common codes

#### `/edit-samples` - Edit Sample Questions
```
/edit-samples
```
- Opens editor with current content
- Team members can modify the entire file
- Changes are saved to `sample_questions.md`
- Persists across sessions
- 5-minute timeout for editing

### 3. **Updated Help**
- `/help` command now includes `/samples` and `/edit-samples`
- Shows `|` separator pattern example
- Clear instructions for team collaboration

---

## How to Use

### View Sample Questions
1. Type `/samples` in chat
2. Browse through 12 categories of examples
3. Copy any question to use it
4. Modify with your own data/states/years

### Edit Sample Questions
1. Type `/edit-samples` in chat
2. System shows current content (first 500 chars)
3. Paste complete new content in response
4. System saves to file
5. Type `/samples` to verify changes

### File Management
- **Direct Edit**: Edit `sample_questions.md` in any text editor
- **Git Track**: File can be version controlled
- **Backup**: Save copies before major changes
- **Share**: Commit to git for team collaboration

---

## Sample Questions Categories

1. **Error Analysis by Type** - Element codes, error patterns
2. **Errors by Household Characteristics** - Elderly, children, disabled
3. **Income-Related Errors** - Wages, SSI, unemployment
4. **State-Level Analysis** - Geographic patterns, policy comparisons
5. **Household Composition** - Size, member eligibility
6. **Benefit Amount Analysis** - Max benefits, thresholds
7. **Deduction Errors** - Shelter, medical, standard
8. **Agency vs Client Responsibility** - Root cause analysis
9. **Time-Based Analysis** - Trends, year-over-year
10. **Advanced Analysis** - Complex queries, risk profiles
11. **Root Cause Investigation** - Element + nature combinations
12. **Practical Management** - Dollar exposure, trends

Plus **Quick Reference** section with common codes.

---

## Example Questions Included

### Basic Format
```
What are the most common error types?
Show income errors by state
```

### With Separator (Focused Analysis)
```
What are the most common error types? | Focus on the top 3 and explain possible root causes

Show errors by element code | Compare income errors (311-346) vs deduction errors (361-366)
```

### Advanced
```
Show overissuance cases with high income uncertainty | Calculate benefit to max allotment ratio and flag outliers

Find income errors for categorically eligible households | Should they have income verification?
```

---

## Team Collaboration Workflow

### Option 1: Use `/edit-samples` Command
```
1. Team member types /edit-samples
2. Reviews current content
3. Adds new questions to appropriate category
4. Submits updated content
5. Questions immediately available to all users
```

### Option 2: Edit File Directly
```
1. Open sample_questions.md in editor
2. Make changes
3. Save file
4. (Optional) Commit to git
5. Changes available immediately (no restart needed)
```

### Option 3: Git Workflow
```
1. Edit sample_questions.md locally
2. Commit changes with descriptive message
3. Push to repository
4. Team pulls latest version
5. Everyone has updated questions
```

---

## File Structure

```markdown
# Sample Questions for SnapAnalyst

Use the | separator...

---

## 1. Error Analysis by Type

### Basic Questions
\`\`\`
Question 1
Question 2
\`\`\`

### With Focused Analysis
\`\`\`
Question | Analysis focus
\`\`\`

---

## 2. Next Category
...
```

---

## Benefits

### For Teams
- ✅ **Centralized Knowledge**: All common queries in one place
- ✅ **Easy Discovery**: New team members see best practices
- ✅ **Living Document**: Evolves with team needs
- ✅ **No Code Required**: Edit plain text markdown

### For Users
- ✅ **Quick Start**: Copy-paste working examples
- ✅ **Learn by Example**: See `|` separator in action
- ✅ **Code Reference**: Common element/nature codes included
- ✅ **Research-Based**: Questions aligned with QC best practices

### For Management
- ✅ **Standardization**: Everyone uses similar query patterns
- ✅ **Training Tool**: Built-in documentation
- ✅ **Collaboration**: Team builds institutional knowledge
- ✅ **Version Control**: Track what queries are most useful

---

## Technical Details

### File Location
```
/Users/eric/Devl/Cursor/_private/SnapAnalyst/sample_questions.md
```

### Command Implementations

**View Command** (`handle_samples_command`):
- Reads `sample_questions.md`
- Displays in formatted message
- Shows tip about editing

**Edit Command** (`handle_edit_samples_command`):
- Loads current content
- Uses `AskUserMessage` for input
- Saves complete new content
- Confirms save with file stats

### No Restart Required
- Changes take effect immediately
- Next `/samples` call shows updated content
- File is read fresh each time

---

## Future Enhancements (Not Implemented)

These could be added later:
- ❌ Syntax validation (check for valid markdown)
- ❌ Preview before save
- ❌ Append mode (add without replacing all)
- ❌ Category-specific editing
- ❌ Search within samples
- ❌ Usage tracking (which questions are most copied)
- ❌ Template generator (fill-in-the-blank questions)

---

## Testing

### Test 1: View Samples
```
Command: /samples
Expected: Shows all 12 categories with examples
```

### Test 2: Edit Samples
```
Command: /edit-samples
Action: Add new question to category 1
Expected: File saved, confirmation shown
Verify: /samples shows new question
```

### Test 3: File Edit
```
Action: Edit sample_questions.md directly
Change: Add custom category
Expected: /samples shows custom category immediately
```

### Test 4: Team Collaboration
```
User A: /edit-samples (adds questions)
User B: /samples (sees User A's additions)
Expected: Changes visible to all users
```

---

## Maintenance

### Regular Updates
- Review quarterly for relevance
- Add frequently asked questions
- Remove outdated examples
- Update code references as schema changes

### Version Control
```bash
# Commit changes
git add sample_questions.md
git commit -m "Add new income error analysis questions"
git push

# Team pulls updates
git pull
```

### Backup
```bash
# Create backup before major changes
cp sample_questions.md sample_questions.backup.md
```

---

## Summary

The editable sample questions feature provides:
1. ✅ **Built-in documentation** accessible via `/samples`
2. ✅ **Team collaboration** through `/edit-samples` or direct file editing  
3. ✅ **Research-based examples** aligned with QC error analysis best practices
4. ✅ **Living knowledge base** that grows with team experience
5. ✅ **Zero configuration** - works out of the box with sensible defaults

**Ready to use now!** Type `/samples` in the chat to see the questions.
