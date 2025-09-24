# Dynamic Badge System for Popcorn Club

This document describes the dynamic badge system implemented in the Popcorn Club Odoo module. The system allows administrators to create badges with flexible rules that automatically evaluate user achievements.

## Overview

The badge system consists of two main models:
- **Badge**: Represents a badge with name, description, image, and associated rules
- **BadgeRule**: Defines the criteria that must be met to earn a badge

## Features

### 1. Dynamic Badge Creation
- Create badges with custom names, descriptions, and images
- Support for multiple languages (translatable fields)
- Active/inactive status for badges

### 2. Flexible Rule System
- Rules can be based on any model in the system (res.partner, event.event, etc.)
- Dynamic field selection based on the chosen model
- Multiple operators: =, !=, >, <, >=, <=, in, not in, like, ilike
- Support for multiple rules per badge (ALL rules must be met)

### 3. Automatic Evaluation
- Real-time evaluation of badge criteria
- Computed fields that show earned status
- Context-aware evaluation for different users

### 4. Portal Integration
- Dedicated "My Badges" page in customer portal
- Visual distinction between earned and unearned badges
- Detailed badge view with requirements breakdown
- Responsive design for mobile devices

## Models

### Badge Model (`popcorn.badge`)
```python
- name: Char (required, translatable)
- description: Text (translatable)
- image: Binary (badge image)
- image_filename: Char (image filename)
- badge_rule_ids: One2many to badge rules
- active: Boolean (default: True)
- earned: Boolean (computed field)
```

### BadgeRule Model (`popcorn.badge.rule`)
```python
- name: Char (required, translatable)
- badge_id: Many2one to badge
- sequence: Integer (for ordering)
- model_id: Many2one to ir.model (required)
- field_id: Many2one to ir.model.fields (required)
- operator: Selection (comparison operator)
- value: Char (threshold value)
- active: Boolean (default: True)
- description: Text (translatable)
```

### Partner Extensions (`res.partner`)
```python
- badge_ids: Many2many (all available badges)
- earned_badge_ids: Many2many (earned badges)
```

## Usage Examples

### Creating a Badge

1. **Navigate to Badges**: Go to Popcorn Club > Badges
2. **Create New Badge**: Click "Create" and fill in:
   - Name: "Event Enthusiast"
   - Description: "Attend 5 or more events"
   - Upload an image (optional)
3. **Add Rules**: In the "Badge Rules" tab, create rules:
   - Model: Event Registration
   - Field: Partner
   - Operator: >=
   - Value: 5

### Supported Models and Fields

The system supports rules based on:
- **res.partner**: User profile fields (email, phone, etc.)
- **event.event**: Event information
- **event.registration**: Event registrations
- **popcorn.membership**: Membership data
- Any other model in the system

### Rule Examples

1. **First Event Badge**:
   - Model: Event Registration
   - Field: Partner
   - Operator: >=
   - Value: 1

2. **Complete Profile Badge**:
   - Rule 1: Model: Partner, Field: Email, Operator: !=, Value: False
   - Rule 2: Model: Partner, Field: Phone, Operator: !=, Value: False

3. **VIP Member Badge**:
   - Model: Membership
   - Field: Partner
   - Operator: >=
   - Value: 1

## Portal Pages

### My Badges Page (`/my/badges`)
- Displays all available badges
- Shows earned/unearned status
- Responsive grid layout
- Click to view detailed requirements

### Badge Detail Page (`/my/badge/<id>`)
- Detailed badge information
- Requirements breakdown
- Progress indicators
- Visual status indicators

## Styling

The system includes comprehensive CSS styling:
- **Earned badges**: Full opacity, green accents
- **Unearned badges**: Reduced opacity, grayscale filter
- **Responsive design**: Mobile-friendly layouts
- **Animations**: Smooth transitions and hover effects

## Security

Access control is implemented through:
- **System Administrators**: Full CRUD access to badges and rules
- **Regular Users**: Read-only access to badges
- **Portal Users**: Read-only access to badges

## Technical Implementation

### Evaluation Logic
The badge evaluation happens in real-time using computed fields:
```python
@api.depends_context('uid')
def _compute_earned(self):
    for badge in self:
        if self.env.context.get('uid'):
            partner = self.env.user.partner_id
            badge.earned = badge._evaluate_badge_for_partner(partner)
```

### Rule Evaluation
Each rule is evaluated independently:
```python
def _evaluate_rule_for_partner(self, partner):
    # Get the model and field
    # Handle different model types
    # Convert values to appropriate types
    # Evaluate the condition
    return self._evaluate_condition(field_value, operator, comparison_value)
```

## Sample Data

The module includes sample badges:
- **First Event**: For attending the first event
- **Event Enthusiast**: For attending 5+ events
- **VIP Member**: For having an active membership
- **Social Butterfly**: For having a complete profile

## Customization

### Adding New Models
To support new models in badge rules:
1. Add the model to the domain in `model_id` field
2. Update the evaluation logic in `_evaluate_rule_for_partner`
3. Test with sample data

### Custom Operators
To add new operators:
1. Add to the selection list in `operator` field
2. Implement logic in `_evaluate_condition` method
3. Update documentation

### Styling Customization
Modify `static/src/css/popcorn_badge_styles.css` to:
- Change colors and themes
- Adjust layout and spacing
- Add custom animations
- Modify responsive breakpoints

## Troubleshooting

### Common Issues

1. **Badges not showing as earned**:
   - Check if rules are active
   - Verify model and field selections
   - Test rule evaluation manually

2. **Portal page not loading**:
   - Ensure controller is properly registered
   - Check template inheritance
   - Verify CSS assets are loaded

3. **Images not displaying**:
   - Check image format (PNG/JPG recommended)
   - Verify file size limits
   - Ensure proper base64 encoding

### Debug Mode
Enable debug mode to see detailed evaluation logs:
```python
import logging
_logger = logging.getLogger(__name__)
_logger.info(f"Evaluating badge {self.name} for partner {partner.name}")
```

## Future Enhancements

Potential improvements:
- Badge categories and collections
- Progress tracking for partial completion
- Badge expiration dates
- Social sharing features
- Achievement notifications
- Badge leaderboards
- Custom badge templates

## Support

For technical support or feature requests, please contact the development team or create an issue in the project repository.
