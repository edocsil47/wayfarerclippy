from playhouse.apsw_ext import *
from playhouse.sqlite_ext import JSONField
from playhouse.migrate import *


class ClippyDB:
    _db = Proxy()
    _migrator = None
    @classmethod
    def start(cls, db_path):
        handle = APSWDatabase(db_path, pragmas={
            'journal_mode': 'wal',
            'cache_size': -1 * 64000,
            'foreign_keys': 1,
            'ignore_check_constraints': 0
        })
        cls._db.initialize(handle)
        # ensure db matches current schema
        cls._db.create_tables([
            ForumUserTable, CommentTable, ContestTable, DiscussionPostTable,
            PermsTimerTable, ProfileTable, ThroneRoundTable
        ])
        cls.init()
        cls._migrator = SqliteMigrator(cls._db)

    @classmethod
    def stop(cls):
        return cls._db.close()

    @classmethod
    def init(cls):
        pass


class BaseModel(Model):
    class Meta:
        database = ClippyDB._db


class ForumUserTable(BaseModel):
    username = TextField(index=True)

    class Meta:
        constraints = [SQL('UNIQUE(username)')]


class CommentTable(BaseModel):
    commentid = BigIntegerField(index=True)
    forumuser = ForeignKeyField(ForumUserTable, field=ForumUserTable.username, backref='Comment', index=True)
    commenttext = TextField()

    class Meta:
        constraints = [SQL('UNIQUE(commentid)')]


class DiscussionPostTable(BaseModel):
    discussionpostid = BigIntegerField(index=True)
    forumuser = ForeignKeyField(ForumUserTable, field=ForumUserTable.username, backref='DiscussionPost', index=True)
    discussionposttext = TextField()

    class Meta:
        constraints = [SQL('UNIQUE(discussionpostid)')]


class PermsTimerTable(BaseModel):
    permstimerid = AutoField()
    name = TextField(index=True)
    time_utc = BigIntegerField()
    finished = BitField()
    channel_id = BigIntegerField()
    guild_id = BigIntegerField()
    config = JSONField()

    class Meta:
        constraints = [SQL('UNIQUE(name)')]


class ThroneRoundTable(BaseModel):
    round_number = IntegerField(index=True)
    start_time = BigIntegerField()
    end_time = BigIntegerField()
    active = BooleanField()
    guild_id = BigIntegerField()


class ThroneRound:
    def __init__(self, round_number, start_time, end_time, active, guild_id):
        self.round_number = round_number
        self.start_time = start_time
        self.end_time = end_time
        self.active = active
        self.guild_id = guild_id


class ProfileTable(BaseModel):
    user_id = BigIntegerField(index=True)
    badge_count = IntegerField(null=True, default=0)
    friendcode = TextField(null=True)
    first_saturdays = IntegerField(null=True, default=0)
    review_contests = IntegerField(null=True, default=0)

    class Meta:
        constraints = [SQL('UNIQUE(user_id)')]


class ContestTable(BaseModel):
    id = AutoField()
    user_id = ForeignKeyField(ProfileTable, field=ProfileTable.user_id, backref='contests', index=True)
    contest_name = TextField(null=True)
    win_title = TextField(null=True)


class StatsTable(BaseModel):
    id = AutoField()
    user_id = ForeignKeyField(ProfileTable, field=ProfileTable.user_id, backref='stats', index=True)
    date_submitted = BigIntegerField(index=True)
    reviews = IntegerField(null=True, default=0)
    agreements = IntegerField(null=True, default=0)
    accepted = IntegerField(null=True, default=0)
    rejected = IntegerField(null=True, default=0)
    duplicate = IntegerField(null=True, default=0)
    other = IntegerField(null=True, default=0)
    upgrades_available = IntegerField(null=True, default=0)
    upgrades_redeemed = IntegerField(null=True, default=0)
    current_progress = IntegerField(null=True, default=0)
    extended_type = TextField(null=True)
    rating = TextField(null=True)


class StatsProfileInstance:
    def __init__(self, user_id, badge_count, friendcode, first_saturdays, review_contests,
                 date_submitted, reviews, agreements, accepted, rejected, duplicate, other,
                 upgrades_available, upgrades_redeemed, current_progress, extended_type, rating):
        self.user_id = user_id
        self.badge_count = badge_count
        self.friendcode = friendcode
        self.first_saturdays = first_saturdays
        self.review_contests = review_contests
        self.date_submitted = date_submitted
        self.reviews = reviews
        self.agreements = agreements
        self.accepted = accepted
        self.rejected = rejected
        self.duplicate = duplicate
        self.other = other

        self.upgrades_available = upgrades_available
        self.upgrades_redeemed = upgrades_redeemed
        self.current_progress = current_progress
        self.extended_type = extended_type
        self.rating = rating
