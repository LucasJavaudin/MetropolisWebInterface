from django.db import models
from django.conf import settings

### Standard tables ###


class Matrices(models.Model):
    name = models.CharField(max_length=50, default='', blank=True, null=True)
    comment = models.CharField(max_length=100, default='', blank=True,
                               null=True)
    defaultValue = models.FloatField(default=0)
    total = models.FloatField(default=0)
    dimension = models.SmallIntegerField(default=2)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Matrices'


class Network(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    comment = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Network'


class FunctionSet(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    comment = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'FunctionSet'


class Function(models.Model):
    name = models.CharField(
        max_length=50,
        default='',
        help_text='Name of the congestion function',
        blank=True,
        null=True,
    )
    vdf_id = models.IntegerField('Link id type', default=0)
    expression = models.TextField(
        default='3600*(length/speed)',
        help_text='Expression of the congestion function'
    )
    user_id = models.IntegerField(default=0, verbose_name='Id')
    functionset = models.ManyToManyField(
        FunctionSet,
        db_table='FunctionSet_Function'
    )

    def __str__(self):
        if self.name:
            return self.name
        else:
            return self.expression

    class Meta:
        db_table = 'Function'


class Supply(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    comment = models.CharField(max_length=100, blank=True, null=True)
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        db_column='network'
    )
    functionset = models.ForeignKey(
        FunctionSet,
        on_delete=models.CASCADE,
        db_column='functionset'
    )
    pttimes = models.ForeignKey(
        Matrices,
        on_delete=models.CASCADE,
        db_column='pttimes',
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Supply'


class Distribution(models.Model):
    mean = models.FloatField(default=0)
    std = models.FloatField('Standard Deviation', default=0)
    none = 'NONE'
    uniform = 'UNIFORM'
    normal = 'NORMAL'
    lognormal = 'LOGNORMAL'
    typeChoices = (
        (none, 'Constant'),
        (uniform, 'Uniform'),
        (normal, 'Normal'),
        (lognormal, 'Log-normal')
    )
    type = models.CharField(
        verbose_name='Type',
        max_length=9,
        choices=typeChoices,
        default=none
    )

    def __str__(self):
        return '{}({}, {})'.format(
            self.get_type_display(), self.mean, self.std)

    class Meta:
        db_table = 'Distribution'


class UserType(models.Model):
    name = models.CharField(
        max_length=50,
        default='',
        help_text='Name of the traveler type',
        verbose_name='Traveler type',
    )
    comment = models.CharField(
        max_length=100,
        default='',
        help_text='Optional comment of the traveler type',
        blank=True,
        null=True,
    )
    alphaTI = models.ForeignKey(
        Distribution,
        related_name='alphaTI',
        on_delete=models.CASCADE,
        db_column='alphaTI',
        verbose_name='Alpha TI',
    )
    alphaTP = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='alphaTP',
        db_column='alphaTP',
        verbose_name='Alpha TP'
    )
    beta = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='beta',
        db_column='beta',
        verbose_name='Beta'
    )
    delta = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='delta',
        db_column='delta',
        verbose_name='Delta'
    )
    departureMu = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='departureMu',
        db_column='departureMu',
        verbose_name='Departure Mu'
    )
    gamma = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='gamma',
        db_column='gamma',
        verbose_name='Gamma'
    )
    modeMu = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='modeMu',
        db_column='modeMu',
        verbose_name='Mode Mu'
    )
    penaltyTP = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='penaltyTP',
        db_column='penaltyTP',
        verbose_name='Penalty TP'
    )
    routeMu = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='routeMu',
        db_column='routeMu',
        verbose_name='Route Mu'
    )
    tstar = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        related_name='tstar',
        db_column='tstar',
        verbose_name='t*'
    )
    MuChoices = (
        ('CONSTANT', 'Constant'),
        ('MINTTCOST', 'Free flow travel cost'),
        ('ALPHATI', 'Alpha TI')
    )
    typeOfModeMu = models.CharField(
        verbose_name='Type of Mode Mu',
        max_length=9,
        choices=MuChoices,
        default='CONSTANT',
        help_text=(
            'Specify how the mu is computed (constant, adaptive to alpha or '
            + 'adaptive to free-flow travel cost)'
        )
    )
    typeOfDepartureMu = models.CharField(
        verbose_name='Type of Departure Mu',
        max_length=9,
        choices=MuChoices,
        default='CONSTANT',
        help_text=(
            'Specify how the mu is computed (constant, adaptive to alpha or '
            + 'adaptive to free-flow travel cost)'
        )
    )
    typeOfRouteMu = models.CharField(
        verbose_name='Type of Route Mu',
        max_length=9,
        choices=MuChoices,
        default='CONSTANT',
        help_text=(
            'Specify how the mu is computed (constant, adaptive to alpha or '
            + 'adaptive to free-flow travel cost)'
        )
    )
    typeOfRouteChoiceChoices = (
        ('DETERMINISTIC', 'Deterministic'),
        ('STOCHASTIC', 'Stochastic')
    )
    typeOfRouteChoice = models.CharField(
        verbose_name='Type of Route Choice',
        max_length=13,
        choices=typeOfRouteChoiceChoices,
        default='DETERMINISTIC',
        help_text='Route choice is either deterministic or stochastic'
    )
    booleanChoices = (
        ('true', 'True'),
        ('false', 'False')
    )
    localATIS = models.CharField(
        verbose_name='Local ATIS',
        max_length=5,
        choices=booleanChoices,
        default='true',
        help_text=(
            'Allow travelers to observe congestion on the downstream links '
            + 'when they arrive at an intersection'
        )
    )
    modeChoice = models.CharField(
        verbose_name='Mode Choice',
        max_length=5,
        choices=booleanChoices,
        default='false',
        help_text=(
            'Enable or disable the choice between public transportation and '
            + 'driving'
        )
    )
    modeShortRun = models.CharField(
        verbose_name='Mode Short Run',
        max_length=5,
        choices=booleanChoices,
        default='true',
        help_text=(
            'With short term choice, the generalized cost associated to the '
            + 'car depends on the departure time; with long term choice, it '
            + 'is independent of time'
        )
    )
    commuteTypeChoices = (
        ('MORNING', 'Morning'),
        ('EVENING', 'Evening'),
        # ('SLOPE', 'Slope model (not working yet)'),
    )
    commuteType = models.CharField(
        verbose_name='Commute Type',
        max_length=7,
        choices=commuteTypeChoices,
        default='MORNING',
        help_text=(
            'In morning simulations, the travelers target a desired arrival '
            + 'time; in evening simulations, the travelers target a desired '
            + 'departure time'
        )
    )
    user_id = models.IntegerField(default=-1, verbose_name='Id')

    def __str__(self):
        if self.name:
            string = self.name
        else:
            string = 'Traveler Type ' + str(self.user_id)
        return string

    class Meta:
        db_table = 'UserType'


class Demand(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    comment = models.CharField(max_length=100, blank=True, null=True)
    scale = models.FloatField(default=1)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Demand'


class DemandSegment(models.Model):
    usertype = models.ForeignKey(
        UserType,
        on_delete=models.CASCADE,
        db_column='usertype'
    )
    matrix = models.ForeignKey(
        Matrices,
        on_delete=models.CASCADE,
        db_column='matrix'
    )
    scale = models.FloatField(default=1)
    demand = models.ManyToManyField(Demand, db_table='Demand_DemandSegment')

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'DemandSegment'


class Scenario(models.Model):
    demand = models.ForeignKey(
        Demand,
        on_delete=models.CASCADE,
        db_column='demand'
    )
    supply = models.ForeignKey(
        Supply,
        on_delete=models.CASCADE,
        db_column='supply'
    )
    comment = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Scenario'


class Centroid(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50, default='', null=True, blank=True)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)
    uz1 = models.FloatField(default=0)
    uz2 = models.FloatField(default=0)
    uz3 = models.FloatField(default=0)
    user_id = models.IntegerField(default=0, verbose_name='Id')
    network = models.ManyToManyField(Network, db_table='Network_Centroid')

    def __str__(self):
        if self.name and self.name != 'NULL':
            string = self.name
        else:
            string = 'x: ' + str(self.x) + ', y: ' + str(self.y)
        return string

    class Meta:
        db_table = 'Centroid'


class CentroidSelection(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        db_column='network'
    )
    storetype = models.IntegerField()
    definition = models.TextField()
    centroid = models.ManyToManyField(
        Centroid,
        db_table='CentroidSelection_Centroid'
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'CentroidSelection'


class Crossing(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50, default='', blank=True, null=True)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)
    un1 = models.FloatField(default=0)
    un2 = models.FloatField(default=0)
    un3 = models.FloatField(default=0)
    user_id = models.IntegerField(default=0, verbose_name='Id')
    network = models.ManyToManyField(Network, db_table='Network_Crossing')

    def __str__(self):
        if self.name and self.name != 'NULL':
            string = self.name
        else:
            string = 'x: ' + str(self.x) + ', y: ' + str(self.y)
        return string

    class Meta:
        db_table = 'Crossing'


class CrossingSelection(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        db_column='network'
    )
    storetype = models.IntegerField()
    definition = models.TextField()
    crossing = models.ManyToManyField(
        Crossing,
        db_table='CrossingSelection_Crossing'
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'CrossingSelection'


class Link(models.Model):
    name = models.CharField(
        max_length=50,
        default='',
        help_text='Name (optional)',
        blank=True,
        null=True,
    )
    destination = models.BigIntegerField(
        verbose_name='To',
        help_text='Destination zone'
    )
    lanes = models.FloatField(
        default=1,
        verbose_name='Lanes',
        help_text='Number of lanes'
    )
    length = models.FloatField(
        default=0,
        verbose_name='Length (km)',
        help_text='Length'
    )
    origin = models.BigIntegerField(
        verbose_name='From',
        help_text='Origin zone'
    )
    speed = models.FloatField(
        default=50,
        verbose_name='Speed (km/h)',
        help_text='Speed limitation'
    )
    ul1 = models.FloatField(default=0)
    ul2 = models.FloatField(default=0)
    ul3 = models.FloatField(default=0)
    vdf = models.ForeignKey(
        'Function',
        verbose_name='Congestion function',
        on_delete=models.CASCADE,
        db_column='vdf',
        help_text='Congestion function that describes the congestion model'
    )
    capacity = models.FloatField(
        default=0,
        verbose_name='Capacity (vehicle per hour per lane)',
        help_text='Capacity per lane (in vehicle per hour)'
    )
    dynVol = models.FloatField(default=0)
    dynFlo = models.FloatField(default=0)
    staVol = models.FloatField(default=0)
    network = models.ManyToManyField(Network, db_table='Network_Link')
    user_id = models.IntegerField(default=0, verbose_name='Id')

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Link'


class LinkSelection(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True,
                            verbose_name='Link name')
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        db_column='network'
    )
    storetype = models.IntegerField(default=1)
    definition = models.TextField(blank=True, null=True)
    link = models.ManyToManyField(Link, db_table='LinkSelection_Link')
    user_id = models.IntegerField(default=0, verbose_name='Link id')

    def __str__(self):
        if self.name:
            return self.name
        else:
            return 'LinkSelection ' + str(self.id)

    class Meta:
        db_table = 'LinkSelection'


class Path(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    origin = models.IntegerField()
    destination = models.IntegerField()
    link = models.ManyToManyField(Link, db_table='Path_Link')
    network = models.ManyToManyField(Network, db_table='Network_Path')

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Path'


class Simulation(models.Model):
    name = models.CharField(
        max_length=50,
        default='',
        help_text='Name of the simulation'
    )
    comment = models.CharField(
        verbose_name='Comment (optional)',
        max_length=100,
        default='',
        help_text='Optional comment of the simulation',
        blank=True,
        null=True,
    )
    commInterval = models.IntegerField(default=600)
    commLevel = models.IntegerField(default=1)
    commOutputChoices = (
        ('TO_DB', 'To database'),
        ('TO_FILE', 'To file'),
        ('TO_STD', 'To std')
    )
    commOutput = models.CharField(
        max_length=7,
        choices=commOutputChoices,
        default='TO_DB'
    )
    commStarted = models.DateTimeField(auto_now_add=True)
    host = models.CharField(max_length=255, default='localhost')
    statusChoices = (
        ('READY', 'Ready'),
        ('OVER', 'Over'),
        ('ABORTED', 'Aborted'),
        ('RUNNING', 'Running')
    )
    status = models.CharField(
        max_length=7,
        choices=statusChoices,
        default='READY'
    )
    booleanChoices = (
        ('true', 'True'),
        ('false', 'False')
    )
    incidentsEnabled = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='false'
    )
    advancedDynShpLoops = models.IntegerField(default=10)
    advancedDynShpTreshold = models.IntegerField(default=30)
    advancedLearningSpeed = models.FloatField(default=.1)
    advancedLearningProcessChoices = (
        ('EXPONENTIAL', 'Exponential'),
        ('LINEAR', 'Linear'),
        ('QUADRATIC', 'Quadratic'),
        ('GENETIC', 'Genetic')
    )
    advancedLearningProcess = models.CharField(
        max_length=11,
        choices=advancedLearningProcessChoices,
        default='EXPONENTIAL',
        help_text='Function type for the learning process'
    )
    advancedInfoSizeChoices = (
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High')
    )
    advancedInfoSize = models.CharField(
        max_length=6,
        choices=advancedInfoSizeChoices,
        default='NORMAL',
        help_text='Amount of available informations for users choices'
    )
    advancedStartup = models.IntegerField(
        default=30,
        help_text=(
            'Percentage of iterations while users have extended '
            + 'informations'
        )
    )
    iterations = models.IntegerField(
        default=100,
        help_text='Maximum number of iterations',
    )
    iterations_check = models.BooleanField(
        default=True,
        help_text=(
            'If checked, the simulation stops when the maximum number of '
            + 'iterations is reached'
        )
    )
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        default=1,
        db_column='scenario'
    )
    stacLim = models.FloatField(
        default=.02,
        help_text='Critical value for the convergence criterion',
    )
    stac_check = models.BooleanField(
        verbose_name='Enable EXPECT convergence criterion',
        default=True,
        help_text=(
            'If checked, the simulation stops when the convergence '
            + ' criterion is verified'
        )
    )
    icSimulation = models.ForeignKey(
        'Simulation',
        on_delete=models.SET_NULL,
        db_column='icSimulation',
        blank=True,
        null=True,
        help_text=(
            'Simulation used as an initialization step for the network '
            + 'loading'
        )
    )
    outputArcTimes = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='true'
    )
    outputMOEs = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='true'
    )
    outputArcLoads = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='true'
    )
    outputUsersPaths = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='false'
    )
    outputIterations = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='false'
    )
    outputUsersTimes = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='false'
    )
    feedUsers = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='false'
    )
    log = models.TextField(default='log')
    outputGeneralizedCosts = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='false'
    )
    phi_in_H = models.IntegerField(default=-1)
    phi_in_S = models.IntegerField(default=-1)
    phi_out_H = models.IntegerField(default=-1)
    phi_out_S = models.IntegerField(default=-1)
    ttime_H = models.IntegerField(default=-1)
    ttime_S = models.IntegerField(default=-1)
    users = models.IntegerField(default=-1)
    horizontalQueueing = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='false',
        help_text=(
            'Check to model horizontal queues with a maximal occupancy'
        )
    )
    jamDensity = models.FloatField(
        default=4,
        help_text='Vehicle length for the spillback effect'
    )
    startTime = models.IntegerField(
        default=360,
        help_text=(
            'Starting time of the simulated period (in minutes after '
            + 'midnight)'
        )
    )
    lastRecord = models.IntegerField(
        default=720,
        help_text=(
            'Ending time of the simulated period (in minutes after '
            + 'midnight)'
        )
    )
    interval_choices = (
        (5, '5 min.'),
        (10, '10 min.'),
        (15, '15 min.'),
        (20, '20 min.')
    )
    recordsInterval = models.IntegerField(
        choices=interval_choices,
        default=10,
        help_text='Interval of time at which the results are stored'
    )
    emailOnCompletion = models.CharField(
        max_length=5,
        choices=booleanChoices,
        default='false',
        help_text=(
            'If checked, send an e-mail when the simulation run has ended'
        )
    )
    simpid = models.IntegerField(default=-1)
    shellpid = models.IntegerField(default=-1)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    contact = models.BooleanField(
        verbose_name='Available for contact',
        default=False,
        help_text=(
            'If checked, anyone with access to the simulation will be able to '
            'access your email to contact you.'
        )
    )
    public = models.BooleanField(
        verbose_name='Public simulation',
        default=True,
        help_text=(
            'If checked, the simulation can be seen (but not edited) by'
            + ' everyone'
        )
    )
    environment = models.ForeignKey('Environment', blank=True, null=True,
                                    on_delete=models.CASCADE)
    has_changed = models.BooleanField(default=True)
    locked = models.BooleanField(default=False)
    pinned = models.BooleanField(default=False)
    random_seed = models.IntegerField(
        default=0,
        help_text='Seed used by the random number generator',
    )
    random_seed_check = models.BooleanField(
        default=False,
        help_text=(
            'If checked, the random number generator use the specified seed; '
            'else, a random seed is used'
        ),
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Simulation'


class Policy(models.Model):
    usertype = models.ForeignKey(
        UserType,
        on_delete=models.CASCADE,
        db_column='usertype',
        blank=True,
        null=True,
        help_text='Traveler-type impacted by the policy'
    )
    location = models.ForeignKey(
        'LinkSelection',
        on_delete=models.CASCADE,
        db_column='location',
        help_text='Area where the policy applies'
    )
    baseValue = models.FloatField(default=0, verbose_name='Value')
    timeVector = models.ForeignKey('Vector', on_delete=models.CASCADE,
                                   db_column='timeVector',
                                   related_name='timeVector',
                                   verbose_name='Time',)
    valueVector = models.ForeignKey('Vector', on_delete=models.CASCADE,
                                    db_column='valueVector',
                                    related_name='valueVector', blank=True,
                                    null=True)
    typeChoices = (
        ('BAN', 'Ban'),
        ('PRICING', 'Pricing'),
        ('RESTRAINT', 'Restraint'),
        ('INCIDENT', 'Incident')
    )
    type = models.CharField(
        max_length=9,
        choices=typeChoices,
        default='BAN'
    )
    parameterChoices = (
        ('none', 'None'),
        ('capacity', 'Capacity'),
        ('lanes', 'Lanes'),
        ('speed', 'Speed'),
        ('ul1', 'ul1'),
        ('ul2', 'ul2'),
        ('ul3', 'ul3')
    )
    parameter = models.CharField(
        max_length=8,
        choices=parameterChoices,
        default='none'
    )
    dayStart = models.IntegerField(default=0, blank=True, null=True)
    dayEnd = models.IntegerField(default=0, blank=True, null=True)
    scenario = models.ManyToManyField(Scenario, db_table='Scenario_Policy')

    def get_value_vector(self):
        values = self.valueVector.data
        if not values:
            # Empty valueVector, return baseValue.
            return self.baseValue
        else:
            # Append baseValue at beginning of valueVector.
            return str(self.baseValue) + ',' + self.valueVector.data

    def get_time_vector(self):
        # Append value 0 at beginning of timeVector.
        return self.timeVector.data

    def __str__(self):
        return 'Policy ' + str(self.id)

    class Meta:
        db_table = 'Policy'


class Region(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    points = models.IntegerField(default=0)
    network = models.ManyToManyField(Network, db_table='Network_Region')

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Region'


class Turn(models.Model):
    atnode = models.IntegerField(default=0)
    fromnode = models.IntegerField(default=0)
    tonode = models.IntegerField(default=0)
    capacity = models.FloatField(default=0)
    penalty = models.FloatField(default=0)
    network = models.ManyToManyField(Network, db_table='Network_Turn')

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Turn'


class Matrix(models.Model):
    p = models.ForeignKey(
        Centroid,
        verbose_name='Origin',
        on_delete=models.CASCADE,
        related_name='origin',
        db_column='p',
        default=1
    )
    q = models.ForeignKey(
        Centroid,
        verbose_name='Destination',
        on_delete=models.CASCADE,
        related_name='destination',
        db_column='q',
        default=1
    )
    r = models.FloatField('Population', default=0)
    matrices = models.ForeignKey(Matrices, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Matrix'


class Vector(models.Model):
    data = models.TextField(
        blank=True, null=True, db_column='data', default='')

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Vector'


### Results tables ###


class SimulationMOEs(models.Model):
    simulation = models.IntegerField(default=0)
    day = models.IntegerField(
        default=0, verbose_name='Day',
        help_text='Current day in the simulation'
    )
    runid = models.IntegerField(default=0)
    stac = models.FloatField(
        default=0, verbose_name='STAC (%)',
        help_text=('Criterion based on the relative variations of travel times'
                   + ' from one iteration to the next (in percentage)')
    )
    expect = models.FloatField(
        default=0, verbose_name='EXPECT (%)',
        help_text=('Criterion based on the difference between expected travel '
                   + 'times and effective travel times (in percentage)')
    )
    users = models.IntegerField(
        default=0, verbose_name='Travelers',
        help_text='Total number of travelers in the simulation'
    )
    drivers = models.IntegerField(
        default=0, verbose_name='Drivers',
        help_text='Total number of travelers who chose to travel by car'
    )
    tt0cost = models.FloatField(
        default=0, verbose_name='Free Flow Travel Cost (€)',
        help_text='Average free flow travel cost for drivers (in euros)'
    )
    toll = models.FloatField(
        default=0, verbose_name='Collected Revenues (€)',
        help_text='Sum of all toll revenues (in euros)'
    )
    period = models.FloatField(
        default=0, verbose_name='Peak Period Length (h)',
        help_text='Length of the peak period (in hours)'
    )
    cong = models.FloatField(
        default=0, verbose_name='Congestion (%)',
        help_text=('Average congestion on the links selected by at least one '
                   + 'driver (in percentage)')
    )
    vehkm = models.FloatField(
        default=0, verbose_name='Mileage (10^6 km)',
        help_text='Total mileage of all drivers (in millions of kilometers)'
    )
    speed = models.FloatField(
        default=0, verbose_name='Speed (km/h)',
        help_text='Average speed of drivers (in km/h)'
    )
    narcs = models.FloatField(
        default=0, verbose_name='Number of Roads',
        help_text='Average number of road sections per driver\'s trip'
    )
    ttime = models.FloatField(
        default=0, verbose_name='Travel Time (min)',
        help_text='Average travel time for drivers (in minutes)'
    )
    cost = models.FloatField(
        default=0, verbose_name='Travel Cost (€)',
        help_text='Average travel cost for drivers, including tolls (in euros)'
    )
    surp = models.FloatField(
        default=0, verbose_name='Consumer Surplus (€)',
        help_text='Average accessibility of travelers (in euros)'
    )
    equi = models.FloatField(
        default=0, verbose_name='Equity (€)',
        help_text='Standard error of the consumer surplus (in euros)'
    )
    early = models.FloatField(
        default=0, verbose_name='Mean Early Delay (min)',
        help_text='Average delay of drivers who arrive too early (in minutes)'
    )
    late = models.FloatField(
        default=0, verbose_name='Mean Late Delay (min)',
        help_text='Average delay of drivers who arrive too late (in minutes)'
    )
    scost = models.FloatField(
        default=0, verbose_name='Schedule Delay Cost (€)',
        help_text='Average schedule delay cost for drivers (in euros)'
    )
    earpop = models.FloatField(
        default=0, verbose_name='Early Ratio (%)',
        help_text='Ratio of drivers who arrive too early (in percentage)'
    )
    ontpop = models.FloatField(
        default=0, verbose_name='On-Time Ratio (%)',
        help_text='Ratio of drivers who arrive on time (in percentage)'
    )
    latpop = models.FloatField(
        default=0, verbose_name='Late Ratio (%)',
        help_text='Ratio of drivers who arrive late (in percentage)'
    )

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'SimulationMOEs'


### Website specific tables ###


class SimulationRun(models.Model):
    name = models.CharField(max_length=50)
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    status = models.CharField(max_length=25, default='Preparing')
    start_time = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)
    time_taken = models.DurationField(blank=True, null=True)
    network_output = models.BooleanField(default=False)
    link_output = models.BooleanField(default=False)
    user_output = models.BooleanField(default=False)
    user_path = models.BooleanField(default=False)

    class Meta:
        db_table = 'SimulationRun'


class Event(models.Model):
    title = models.CharField(max_length=300, blank=False, null=False,
                             default='', db_column='name')
    author = models.CharField(max_length=150, blank=False, null=False,
                              default='', db_column='author')
    date = models.DateTimeField(auto_now_add=True, blank=False,
                                db_column='creation_date')
    description = models.TextField(blank=True, null=True,
                                   db_column='description')

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Events'


class Article(models.Model):
    title = models.CharField(max_length=300, blank=False, null=False,
                             default='', db_column='title')
    description = models.TextField(blank=True, null=True,
                                   db_column='description')
    creator = models.CharField(max_length=150, blank=False, null=False,
                               default='', db_column='author')

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Articles'


class ArticleFile(models.Model):
    file = models.FileField(upload_to='articles/', max_length=500, blank=False,
                            null=False, default='')
    file_name = models.CharField(max_length=500)
    file_article = models.ForeignKey(
        Article, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return str(self.id)

    def get_download(self):
        return "<a href='" + self.file.name + "'>" + self.file_name + "</a>"


class Environment(models.Model):
    name = models.CharField(max_length=200)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owner',
    )

    def __str__(self):
        return str(self.name)

    def is_authorised(self, user):
        if user in self.users.all():
            return True
        else:
            return False


class Batch(models.Model):
    name = models.CharField(max_length=50)
    comment = models.CharField(
        max_length=100, default='', blank=True, null=True)
    nb_runs = models.IntegerField(default=2, verbose_name='Number of runs')
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    status = models.CharField(max_length=25, default='Preparing')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)
    time_taken = models.DurationField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'Batch'


class BatchRun(models.Model):
    name = models.CharField(max_length=50, blank=False, null=False)
    comment = models.CharField(
        max_length=100, default='', blank=True, null=True)
    centroid_file = models.FileField(
        upload_to='import_files', blank=True, null=True)
    crossing_file = models.FileField(
        upload_to='import_files', blank=True, null=True)
    function_file = models.FileField(
        upload_to='import_files', blank=True, null=True)
    link_file = models.FileField(
        upload_to='import_files', blank=True, null=True)
    public_transit_file = models.FileField(
        upload_to='import_files', blank=True, null=True)
    traveler_file = models.FileField(
        upload_to='import_files', blank=True, null=True)
    pricing_file = models.FileField(
        upload_to='import_files', blank=True, null=True)
    zip_file = models.FileField(
        upload_to='import_files', blank=True, null=True)
    failed = models.BooleanField(default=False)
    canceled = models.BooleanField(default=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE,
                            blank=True, null=True)

    class Meta:
        db_table = 'BatchRun'
