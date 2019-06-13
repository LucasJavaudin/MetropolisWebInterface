from django import forms
from django.forms import BaseModelFormSet
from django.forms import formset_factory, modelformset_factory
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import *
from .functions import *


#====================
# Forms
#====================

class UserCreationForm(UserCreationForm):
    """Form used to register a new user.
    
    This is a modified version of the Django form. The e-mail field has been
    added.
    """
    email = forms.EmailField(
            label="Email adress",
            required=True,
            help_text="Required.",
    )

    def __init__(self, *args, **kwargs):
        super(UserCreationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = 'Enter username'
        self.fields['email'].widget.attrs['placeholder'] = 'Enter email'
        self.fields['password1'].widget.attrs['placeholder'] = 'Enter password'
        self.fields['password2'].widget.attrs['placeholder'] = \
            'Repeat password'

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    """Form used to log an user in."""
    username = forms.CharField(label='Username')
    password = forms.CharField(label='Password')

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        # Add placeholders.
        self.fields['username'].widget.attrs['placeholder'] = 'Username'
        self.fields['password'].widget = forms.PasswordInput()
        self.fields['password'].widget.attrs['placeholder'] = 'Password'

class CustomCheckboxInput(forms.CheckboxInput):
    """Custom CheckboxInput to work with the mysql database of metropolis."""
    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.check_test = custom_check_test

    def value_from_datadict(self, data, files, name):
        if name not in data:
            # If the checkbox is not checked, return 'false'.
            return 'false'
        else:
            # If the checkbox is checked, return 'true'.
            return 'true'

class BaseSimulationForm(forms.ModelForm):
    """Form to edit basic variables of a simulation (name, comment and public).

    The form is used to create new a simulation, to copy a simulation or to
    edit the variable of an existing simulation.
    """

    #environment = forms.ModelChoiceField(queryset=Environment.objects.none())

    def __init__(self, user, *args, **kwargs):
        super(BaseSimulationForm, self).__init__(*args, **kwargs)
        auth_environments = Environment.objects.filter(users=user)
        self.fields['environment'] = forms.ModelChoiceField(
            queryset=auth_environments, required=False)
        # Field comment is not required.
        self.fields['comment'].required = False

        # Add tooltips.
        for bound_field in self:
            bound_field.field.widget.attrs['title'] = bound_field.help_text

        #if self.fields.widget.att

    class Meta:
        model = Simulation
        fields = ['name', 'comment', 'environment', 'contact', 'public']

class ParametersSimulationForm(forms.ModelForm):
    """Form to edit the parameters of a simulation."""
    def __init__(self, owner=False, *args, **kwargs):
        super(ParametersSimulationForm, self).__init__(*args, **kwargs)
        # Disable all fields if the user is not owner.
        if not owner:
            for field in self.fields:
                self.fields[field].disabled = True
        # Some fields are not required.
        not_required_fields = [
                'horizontalQueueing', 'stac_check', 'iterations_check',
            'stacLim'
        ]
        for field in not_required_fields:
            self.fields[field].required = False
        # Stac, iterations and spillback have an associated input that must be
        # greyed out if the checkbox is not checked.
        self.fields['stac_check'].widget.attrs['onchange'] = \
            'updateInput();'
        self.fields['iterations_check'].widget.attrs['onchange'] = \
            'updateInput();'
        self.fields['horizontalQueueing'].widget.attrs['onchange'] = \
            'updateInput();'
        # Add min and max values.
        self.fields['stacLim'].widget.attrs['min'] = 0
        self.fields['stacLim'].widget.attrs['max'] = 100
        self.fields['iterations'].widget.attrs['min'] = 0
        self.fields['jamDensity'].widget.attrs['min'] = 0
        # Add tooltips.
        for bound_field in self:
            bound_field.field.widget.attrs['title'] = bound_field.help_text

    class Meta:
        model = Simulation
        fields = [
                'stacLim', 'iterations', 'startTime', 'lastRecord',
                'recordsInterval', 'jamDensity', 'advancedLearningProcess',
                'horizontalQueueing', 'stac_check', 'iterations_check',
        ]
        # Metropolis booleans should be checkboxes.
        widgets = {
                'horizontalQueueing': CustomCheckboxInput(),
        }

class RunForm(forms.ModelForm):
    """Form to give a name to a SimulationRun."""
    def save(self, simulation, commit=True):
        # Save the SimulationRun with the specified Simulation.
        instance = super(RunForm, self).save(commit=False)
        instance.simulation = simulation
        if commit:
            instance.save()
        return instance

    class Meta:
        model = SimulationRun
        fields = ['name']

class UserTypeForm(forms.ModelForm):
    """Form to edit an user type, including the distributions."""
    # Add a field to change the scale of the O-D matrix.
    scale = forms.FloatField(min_value=0)
    # Add more fields to define the distributions.
    typeChoices = (
        ('NONE', 'Constant'),
        ('UNIFORM', 'Uniform'),
        ('NORMAL', 'Normal'),
        ('LOGNORMAL', 'Log-normal')
    )
    alphaTI_type = forms.ChoiceField(choices=typeChoices)
    alphaTI_mean = forms.FloatField(min_value=0)
    alphaTI_std = forms.FloatField(min_value=0)
    alphaTP_type = forms.ChoiceField(choices=typeChoices)
    alphaTP_mean = forms.FloatField(min_value=0)
    alphaTP_std = forms.FloatField(min_value=0)
    beta_type = forms.ChoiceField(choices=typeChoices)
    beta_mean = forms.FloatField(min_value=0)
    beta_std = forms.FloatField(min_value=0)
    delta_type = forms.ChoiceField(choices=typeChoices)
    delta_mean = forms.FloatField(min_value=0)
    delta_std = forms.FloatField(min_value=0)
    departureMu_type = forms.ChoiceField(choices=typeChoices)
    departureMu_mean = forms.FloatField(min_value=0)
    departureMu_std = forms.FloatField(min_value=0)
    gamma_type = forms.ChoiceField(choices=typeChoices)
    gamma_mean = forms.FloatField(min_value=0)
    gamma_std = forms.FloatField(min_value=0)
    modeMu_type = forms.ChoiceField(choices=typeChoices)
    modeMu_mean = forms.FloatField(min_value=0)
    modeMu_std = forms.FloatField(min_value=0)
    penaltyTP_type = forms.ChoiceField(choices=typeChoices)
    penaltyTP_mean = forms.FloatField()
    penaltyTP_std = forms.FloatField(min_value=0)
    routeMu_type = forms.ChoiceField(choices=typeChoices)
    routeMu_mean = forms.FloatField(min_value=0)
    routeMu_std = forms.FloatField(min_value=0)
    tstar_type = forms.ChoiceField(choices=typeChoices)
    tstar_mean = forms.FloatField(min_value=0)
    tstar_std = forms.FloatField(min_value=0)

    def __init__(self, *args, **kwargs):
        super(UserTypeForm, self).__init__(*args, **kwargs)
        # Some fields are not required.
        not_required_fields = [
                'name', 'comment', 'modeChoice', 'modeShortRun', 'localATIS',
        ]
        for field in not_required_fields:
            self.fields[field].required = False
        # Add tooltips.
        for bound_field in self:
            bound_field.field.widget.attrs['title'] = bound_field.help_text
        self.fields['scale'].widget.attrs['title'] = (
            'All values in the O-D matrix of the traveler type are multiplied '
            + 'by the scale value'
        )
        # Add initial scale value.
        self.fields['scale'].initial = \
            self.instance.demandsegment_set.first().scale
        # Add initial values for the distribution fields.
        self.fields['alphaTI_type'].initial = self.instance.alphaTI.type
        self.fields['alphaTI_mean'].initial = self.instance.alphaTI.mean
        self.fields['alphaTI_std'].initial = self.instance.alphaTI.std
        self.fields['alphaTP_type'].initial = self.instance.alphaTP.type
        self.fields['alphaTP_mean'].initial = self.instance.alphaTP.mean
        self.fields['alphaTP_std'].initial = self.instance.alphaTP.std
        self.fields['beta_type'].initial = self.instance.beta.type
        self.fields['beta_mean'].initial = self.instance.beta.mean
        self.fields['beta_std'].initial = self.instance.beta.std
        self.fields['delta_type'].initial = self.instance.delta.type
        self.fields['delta_mean'].initial = self.instance.delta.mean
        self.fields['delta_std'].initial = self.instance.delta.std
        self.fields['departureMu_type'].initial = \
            self.instance.departureMu.type
        self.fields['departureMu_mean'].initial = \
            self.instance.departureMu.mean
        self.fields['departureMu_std'].initial = self.instance.departureMu.std
        self.fields['gamma_type'].initial = self.instance.gamma.type
        self.fields['gamma_mean'].initial = self.instance.gamma.mean
        self.fields['gamma_std'].initial = self.instance.gamma.std
        self.fields['modeMu_type'].initial = self.instance.modeMu.type
        self.fields['modeMu_mean'].initial = self.instance.modeMu.mean
        self.fields['modeMu_std'].initial = self.instance.modeMu.std
        self.fields['penaltyTP_type'].initial = self.instance.penaltyTP.type
        self.fields['penaltyTP_mean'].initial = self.instance.penaltyTP.mean
        self.fields['penaltyTP_std'].initial = self.instance.penaltyTP.std
        self.fields['routeMu_type'].initial = self.instance.routeMu.type
        self.fields['routeMu_mean'].initial = self.instance.routeMu.mean
        self.fields['routeMu_std'].initial = self.instance.routeMu.std
        self.fields['tstar_type'].initial = self.instance.tstar.type
        self.fields['tstar_mean'].initial = self.instance.tstar.mean
        self.fields['tstar_std'].initial = self.instance.tstar.std

    def save(self, commit=True):
        # Save the usertype.
        instance = super(UserTypeForm, self).save(commit=commit)
        # Save the scale.
        demandsegment = instance.demandsegment_set.all()
        if commit:
            demandsegment.update(scale=self.cleaned_data['scale'])
        # Save the distributions.
        instance.alphaTI.type = self.cleaned_data['alphaTI_type']
        instance.alphaTI.mean = self.cleaned_data['alphaTI_mean']
        instance.alphaTI.std = self.cleaned_data['alphaTI_std']
        if commit:
            instance.alphaTI.save()
        instance.alphaTP.type = self.cleaned_data['alphaTP_type']
        instance.alphaTP.mean = self.cleaned_data['alphaTP_mean']
        instance.alphaTP.std = self.cleaned_data['alphaTP_std']
        if commit:
            instance.alphaTP.save()
        instance.beta.type = self.cleaned_data['beta_type']
        instance.beta.mean = self.cleaned_data['beta_mean']
        instance.beta.std = self.cleaned_data['beta_std']
        if commit:
            instance.beta.save()
        instance.delta.type = self.cleaned_data['delta_type']
        instance.delta.mean = self.cleaned_data['delta_mean']
        instance.delta.std = self.cleaned_data['delta_std']
        if commit:
            instance.delta.save()
        instance.departureMu.type = self.cleaned_data['departureMu_type']
        instance.departureMu.mean = self.cleaned_data['departureMu_mean']
        instance.departureMu.std = self.cleaned_data['departureMu_std']
        if commit:
            instance.departureMu.save()
        instance.gamma.type = self.cleaned_data['gamma_type']
        instance.gamma.mean = self.cleaned_data['gamma_mean']
        instance.gamma.std = self.cleaned_data['gamma_std']
        if commit:
            instance.gamma.save()
        instance.modeMu.type = self.cleaned_data['modeMu_type']
        instance.modeMu.mean = self.cleaned_data['modeMu_mean']
        instance.modeMu.std = self.cleaned_data['modeMu_std']
        if commit:
            instance.modeMu.save()
        instance.penaltyTP.type = self.cleaned_data['penaltyTP_type']
        instance.penaltyTP.mean = self.cleaned_data['penaltyTP_mean']
        instance.penaltyTP.std = self.cleaned_data['penaltyTP_std']
        if commit:
            instance.penaltyTP.save()
        instance.routeMu.type = self.cleaned_data['routeMu_type']
        instance.routeMu.mean = self.cleaned_data['routeMu_mean']
        instance.routeMu.std = self.cleaned_data['routeMu_std']
        if commit:
            instance.routeMu.save()
        instance.tstar.type = self.cleaned_data['tstar_type']
        instance.tstar.mean = self.cleaned_data['tstar_mean']
        instance.tstar.std = self.cleaned_data['tstar_std']
        if commit:
            instance.tstar.save()
        return instance

    class Meta:
        model = UserType
        fields = ['name', 'comment', 'typeOfModeMu', 'typeOfDepartureMu',
                  'typeOfRouteMu', 'typeOfRouteChoice', 'localATIS',
                  'modeChoice', 'modeShortRun', 'commuteType']
        # Metropolis booleans should be checkboxes.
        widgets = {
            'modeChoice': CustomCheckboxInput(),
            'modeShortRun': CustomCheckboxInput(),
            'localATIS': CustomCheckboxInput(),
        }

class MatrixForm(forms.ModelForm):
    """Form to edit an OD pair."""
    class Meta:
        model = Matrix
        fields = ['r']

class PolicyForm(forms.ModelForm):
    """Form to edit pricing policy."""
    class Meta:
        model = Policy
        fields = ['usertype','location', 'baseValue','timeVector','valueVector']

class CentroidForm(forms.ModelForm):
    """Form the edit the centroids."""
    def __init__(self, *args, **kwargs):
        super(CentroidForm, self).__init__(*args, **kwargs)
        # Field name is not required.
        self.fields['name'].required = False
        # Add tooltips.
        for bound_field in self:
            bound_field.field.widget.attrs['title'] = bound_field.help_text

    def has_changed(self):
        """Method has_changed() should return True if the form is new even if
        it has not been changed.
        """
        changed_data = super(CentroidForm, self).has_changed()
        # A form is new if it has no id yet.
        is_new = not bool(self.instance.id)
        return bool(changed_data or is_new)

    def save(self, commit=True):
        # If no name is specify, set name to be empty string.
        instance = super(CentroidForm, self).save(commit=False)
        if instance.name == None:
            instance.name = ''
        if commit:
            instance.save()
        return instance

    class Meta:
        model = Centroid
        fields = ['name', 'x', 'y', 'user_id']

class CrossingForm(forms.ModelForm):
    """Form to edit the crossings."""
    def __init__(self, *args, **kwargs):
        super(CrossingForm, self).__init__(*args, **kwargs)
        # Field name is not required.
        self.fields['name'].required = False
        # Add tooltips.
        for bound_field in self:
            bound_field.field.widget.attrs['title'] = bound_field.help_text

    def has_changed(self):
        """Method has_changed() should return True if the form is new even if
        it has not been changed.
        """
        changed_data = super(CrossingForm, self).has_changed()
        is_new = not bool(self.instance.id)
        return bool(changed_data or is_new)

    def save(self, commit=True):
        # If no name is specify, set name to be empty string.
        instance = super(CrossingForm, self).save(commit=False)
        if instance.name == None:
            instance.name = ''
        if commit:
            instance.save()
        return instance

    class Meta:
        model = Crossing
        fields = ['name', 'x', 'y', 'user_id']

class LinkForm(forms.ModelForm):
    """Form to edit the links."""
    origin = forms.ChoiceField()
    destination = forms.ChoiceField()

    def __init__(self, simulation, *args, **kwargs):
        super(LinkForm, self).__init__(*args, **kwargs)
        # Field name is not required.
        self.fields['name'].required = False
        # The choices for origin and destination are the nodes of the Network.
        node_choices = get_node_choices(simulation)
        self.fields['origin'].choices = node_choices
        self.fields['destination'].choices = node_choices
        # The choices for vdf are the functions of the associated function set.
        self.fields['vdf'].queryset = Function.objects.filter(
                functionset__supply__scenario__simulation=simulation
        )
        # Add tooltips.
        for bound_field in self:
            bound_field.field.widget.attrs['title'] = bound_field.help_text

    def has_changed(self):
        """Method has_changed() should return True if the form is new even if
        it has not been changed.
        """
        changed_data = super(LinkForm, self).has_changed()
        is_new = not bool(self.instance.id)
        return bool(changed_data or is_new)

    def save(self, commit=True):
        # If no name is specify, set name to be empty string.
        instance = super(LinkForm, self).save(commit=False)
        if instance.name == None:
            instance.name = ''
        if commit:
            instance.save()
        return instance

    class Meta:
        model = Link
        fields = [
                'name', 'origin', 'destination', 'lanes', 'length', 'speed',
                'vdf', 'capacity', 'user_id'
        ]

class FunctionForm(forms.ModelForm):
    """Form to edit the congestion functions."""
    def __init__(self, *args, **kwargs):
        super(FunctionForm, self).__init__(*args, **kwargs)
        # Field name is not required.
        self.fields['name'].required = False
        # Add tooltips.
        for bound_field in self:
            bound_field.field.widget.attrs['title'] = bound_field.help_text

    def has_changed(self):
        """Method has_changed() should return True if the form is new even if
        it has not been changed.
        """
        changed_data = super(FunctionForm, self).has_changed()
        is_new = not bool(self.instance.id)
        return bool(changed_data or is_new)

    class Meta:
        model = Function
        fields = ['name', 'expression', 'user_id']
        widgets = {
                'expression': forms.TextInput(),
        }

class ImportForm(forms.Form):
    """Simple form to import a file."""
    import_file = forms.FileField()

class CentroidModelFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.simulation = kwargs.pop('simulation')
        super().__init__(*args, **kwargs)

    def clean(self):
        """Checks that no two nodes have the same user_id."""
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on
            # its own
            return
        crossings = get_query('crossing', self.simulation)
        user_ids = list(crossings.values_list('user_id', flat=True))
        for form in self.forms:
            user_id = form.cleaned_data['user_id']
            delete = form.cleaned_data['DELETE']
            if not delete:
                if user_id in user_ids:
                    raise forms.ValidationError(
                        'Two nodes (zones and intersections) cannot have the same '
                        'id (id: {}).'.format(user_id)
                    )
                user_ids.append(user_id)

class CrossingModelFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.simulation = kwargs.pop('simulation')
        super().__init__(*args, **kwargs)

    def clean(self):
        """Checks that no two nodes have the same user_id."""
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on
            # its own
            return
        centroids = get_query('centroid', self.simulation)
        user_ids = list(centroids.values_list('user_id', flat=True))
        for form in self.forms:
            user_id = form.cleaned_data['user_id']
            delete = form.cleaned_data['DELETE']
            if not delete:
                if user_id in user_ids:
                    raise forms.ValidationError(
                        'Two nodes (zones and intersections) cannot have the same '
                        'id (id: {}).'.format(user_id)
                    )
                user_ids.append(user_id)

class LinkModelFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.simulation = kwargs.pop('simulation')
        super().__init__(*args, **kwargs)

    def clean(self):
        """Checks that no two links have the same user_id."""
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on
            # its own
            return
        user_ids = []
        for form in self.forms:
            user_id = form.cleaned_data['user_id']
            delete = form.cleaned_data['DELETE']
            if not delete:
                if user_id in user_ids:
                    raise forms.ValidationError(
                        'Two links cannot have the same id '
                        '(id: {}).'.format(user_id)
                    )
                user_ids.append(user_id)

class FunctionModelFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.simulation = kwargs.pop('simulation')
        super().__init__(*args, **kwargs)

    def clean(self):
        """Checks that no two functions have the same user_id."""
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on
            # its own
            return
        user_ids = []
        for form in self.forms:
            user_id = form.cleaned_data['user_id']
            delete = form.cleaned_data['DELETE']
            if not delete:
                if user_id in user_ids:
                    raise forms.ValidationError(
                        'Two congestion functions cannot have the same id '
                        '(id: {}).'.format(user_id)
                    )
                user_ids.append(user_id)

class EventForm(forms.Form):
    title = forms.CharField()
    description = forms.CharField(required=False, widget=forms.Textarea(
        attrs={"cols":20}))

class ArticleForm(forms.Form):
    title = forms.CharField()
    description = forms.CharField(required=False, widget=forms.Textarea(
        attrs={"cols":20}))
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={
        'multiple': True}), required=False)

class EnvironmentForm(forms.Form):
    name = forms.CharField(max_length=200)

class EnvironmentUserAddForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)

    def is_valid(self):
        valid = super(EnvironmentUserAddForm, self).is_valid()

        if not valid:
            return valid

        try:
            user = User.objects.get(username = self.cleaned_data['username'])

        except User.DoesNotExist:
            self._errors['no_user'] = 'User does not exist'
            return False

        return True

#====================
# FormSets
#====================

MatrixFormSet = modelformset_factory(
    Matrix,
    form=MatrixForm,
    extra=0
)

PolicyFormSet = modelformset_factory(
    Policy,
    form=PolicyForm,
    extra=0,
)

CentroidFormSet = modelformset_factory(
    Centroid, 
    form=CentroidForm,
    formset=CentroidModelFormSet,
    can_delete=True,
    extra=0,
)

CentroidFormSetExtra = modelformset_factory(
    Centroid, 
    form=CentroidForm,
    formset=CentroidModelFormSet,
    can_delete=True,
    extra=1,
)

CrossingFormSet = modelformset_factory(
    Crossing, 
    form=CrossingForm,
    formset=CrossingModelFormSet,
    can_delete=True,
    extra=0,
)

CrossingFormSetExtra = modelformset_factory(
    Crossing, 
    form=CrossingForm,
    formset=CrossingModelFormSet,
    can_delete=True,
    extra=1,
)

LinkFormSet = modelformset_factory(
    Link, 
    form=LinkForm,
    formset=LinkModelFormSet,
    can_delete=True,
    extra=0,
)

LinkFormSetExtra = modelformset_factory(
    Link, 
    form=LinkForm,
    formset=LinkModelFormSet,
    can_delete=True,
    extra=1,
)

FunctionFormSet = modelformset_factory(
    Function,
    form=FunctionForm,
    formset=FunctionModelFormSet,
    can_delete=True,
    extra=0,
)

FunctionFormSetExtra = modelformset_factory(
    Function,
    form=FunctionForm,
    formset=FunctionModelFormSet,
    can_delete=True,
    extra=1,
)
