# Phase 2.2: PostgreSQL Schema Validation - Practical Runbook

**Status**: READY TO EXECUTE
**Prerequisites**: Docker daemon running, 15-20 minutes
**Database**: PostgreSQL 15 Alpine with 1500+ test records

---

## STEP 1: Start PostgreSQL Container

```bash
cd /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/educational-apps-go

# Start PostgreSQL (schema loads automatically)
docker-compose -f deploy/docker-compose.yml up postgres

# Expected output:
# - educational-apps-postgres: starting
# - PostgreSQL listening on port 5432
# - Schema migrations loading from ./migrations/
# - Status: healthy ✅
```

**Wait for**: "PostgreSQL ready for connections"

---

## STEP 2: Verify Schema Loaded

```bash
# In new terminal, connect to database
docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c "\dt"

# Expected output: 26 tables
# ✅ users
# ✅ sessions
# ✅ reading_lessons
# ✅ reading_word_mastery
# ✅ reading_comprehension_answers
# ✅ math_problems
# ✅ math_attempts
# ✅ math_progress
# ✅ piano_notes
# ✅ piano_exercises
# ✅ piano_attempts
# ✅ typing_exercises
# ✅ typing_attempts
# ✅ typing_progress
# ✅ comprehension_passages
# ✅ comprehension_questions
# ✅ comprehension_answers
```

---

## STEP 3: Verify Indexes Created

```bash
docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c "SELECT COUNT(*) as index_count FROM pg_indexes WHERE schemaname='public';"

# Expected: 13+ indexes
# If < 13: Schema didn't load completely ❌
```

---

## STEP 4: Check Foreign Key Constraints

```bash
docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"SELECT constraint_name, constraint_type, table_name
 FROM information_schema.table_constraints
 WHERE table_schema = 'public' AND constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
 ORDER BY constraint_type DESC;"

# Expected: 26 PRIMARY KEY constraints
# Expected: 11 FOREIGN KEY constraints
```

---

## STEP 5: Generate Sample Data

```bash
# Build seed generator (if not already built)
cd /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/educational-apps-go
go build -o bin/seed-database ./cmd/seed-database

# Run seed generator for PostgreSQL
./bin/seed-database --db-type postgres --users 100

# Expected output:
# 🌱 Starting data seeding...
# ✅ Created 100 users
# ✅ Created 10 reading lessons and word mastery records
# ✅ Created 1000 math problems and attempts
# ✅ Created 200 piano exercises and attempts
# ✅ Created 300 typing exercises and attempts
# ✅ Created 150 comprehension passages and answers
# 🎉 Data seeding complete!
```

---

## STEP 6: Verify Data Loaded

```bash
docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"SELECT 'users' as table_name, COUNT(*) as count FROM users
 UNION ALL SELECT 'math_problems', COUNT(*) FROM math_problems
 UNION ALL SELECT 'piano_exercises', COUNT(*) FROM piano_exercises
 UNION ALL SELECT 'typing_exercises', COUNT(*) FROM typing_exercises
 UNION ALL SELECT 'comprehension_passages', COUNT(*) FROM comprehension_passages;"

# Expected counts:
# users: 100
# math_problems: 1000
# piano_exercises: 200
# typing_exercises: 300
# comprehension_passages: 150
```

---

## STEP 7: Data Integrity Tests

### Test 7A: Check for Orphaned Records
```bash
docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"SELECT 'math_attempts with missing problem' as test, COUNT(*) as orphan_count
 FROM math_attempts
 WHERE problem_id NOT IN (SELECT id FROM math_problems)
 UNION ALL
 SELECT 'piano_attempts with missing exercise', COUNT(*)
 FROM piano_attempts
 WHERE exercise_id NOT IN (SELECT id FROM piano_exercises);"

# Expected: All counts = 0 ✅
# Any count > 0 = DATA INTEGRITY ISSUE ❌
```

### Test 7B: Check for Duplicate Unique Values
```bash
docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"SELECT username, COUNT(*) as occurrences
 FROM users
 GROUP BY username
 HAVING COUNT(*) > 1;"

# Expected: No rows returned ✅
# Any rows = DUPLICATE USERNAME ❌
```

### Test 7C: Verify Foreign Key Relationships
```bash
docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"SELECT COUNT(*) as valid_math_attempts
 FROM math_attempts ma
 WHERE EXISTS (SELECT 1 FROM users u WHERE u.id = ma.user_id)
   AND EXISTS (SELECT 1 FROM math_problems mp WHERE mp.id = ma.problem_id);"

# Expected: Should equal total math_attempts count ✅
```

---

## STEP 8: Performance Baseline Queries

```bash
# Query 1: Simple user lookup (should be <5ms)
time docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"SELECT * FROM users WHERE id = 1;"

# Query 2: Join across tables (should be <10ms)
time docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"SELECT u.username, COUNT(ma.id) as attempts
 FROM users u
 LEFT JOIN math_attempts ma ON u.id = ma.user_id
 WHERE u.id <= 10
 GROUP BY u.id, u.username;"

# Query 3: Complex query with aggregation (should be <50ms)
time docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"SELECT u.username,
        COUNT(DISTINCT ma.id) as math_attempts,
        COUNT(DISTINCT pa.id) as piano_attempts,
        COUNT(DISTINCT ta.id) as typing_attempts
 FROM users u
 LEFT JOIN math_attempts ma ON u.id = ma.user_id
 LEFT JOIN piano_attempts pa ON u.id = pa.user_id
 LEFT JOIN typing_attempts ta ON u.id = ta.user_id
 GROUP BY u.id, u.username
 LIMIT 10;"
```

---

## STEP 9: Index Effectiveness

```bash
docker exec -it educational-apps-postgres psql -U postgres -d educational_apps -c \
"EXPLAIN ANALYZE
 SELECT * FROM users WHERE username = 'user_1';"

# Expected: Uses idx_users_username index
# Should show: "Index Scan using idx_users_username"
```

---

## STEP 10: Generate Validation Report

```bash
# After all tests pass, create summary
cat > /tmp/pg_validation_results.txt << 'EOF'
✅ PostgreSQL Schema Validation - PASSED

Schema Status:
- 26 tables created ✅
- 13+ indexes created ✅
- All constraints defined ✅

Data Integrity:
- 0 orphaned records ✅
- 0 duplicate unique values ✅
- All foreign keys valid ✅

Performance:
- Simple query: <5ms ✅
- Join query: <10ms ✅
- Aggregate query: <50ms ✅
- Index utilization: WORKING ✅

Data Loaded:
- 100 users ✅
- 1000 math problems ✅
- 200 piano exercises ✅
- 300 typing exercises ✅
- 150 comprehension passages ✅
- 1500+ total records ✅

✅ VALIDATION COMPLETE - READY FOR PHASE 2.3
EOF

cat /tmp/pg_validation_results.txt
```

---

## Troubleshooting

### Issue: "Schema migrations not loading"
```bash
# Check if migrations directory exists
ls -la /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/educational-apps-go/migrations/

# Verify file permissions
chmod 644 migrations/*.sql

# Restart container
docker-compose -f deploy/docker-compose.yml restart postgres
```

### Issue: "Connection refused"
```bash
# Check if container is running
docker ps | grep postgres

# View logs
docker logs educational-apps-postgres

# Restart
docker-compose -f deploy/docker-compose.yml restart
```

### Issue: "Table already exists"
```bash
# Remove and recreate
docker-compose -f deploy/docker-compose.yml down -v
docker-compose -f deploy/docker-compose.yml up postgres
```

### Issue: "Out of memory"
```bash
# Increase Docker memory allocation
# Docker Desktop → Preferences → Resources → Memory → Set to 4GB+
```

---

## Success Criteria Checklist

- [ ] All 26 tables created
- [ ] All 13+ indexes created
- [ ] Seed data generated (100 users, 1000+ records)
- [ ] 0 orphaned records detected
- [ ] 0 duplicate unique values
- [ ] All foreign key relationships valid
- [ ] Simple query <5ms
- [ ] Join query <10ms
- [ ] Complex query <50ms
- [ ] Index scan confirmed in EXPLAIN ANALYZE

---

## Next: Phase 2.3 - Migration Tool Testing

Once validation passes:
1. Create migration tool Go binary
2. Seed SQLite with same sample data
3. Run dry-run migration
4. Verify data integrity post-migration
5. Compare SQLite vs PostgreSQL query performance

**Estimated time**: 4 hours

---

**Status**: ✅ READY TO EXECUTE
**Prerequisites Checklist**:
- [ ] Docker daemon running
- [ ] Seed data generator built
- [ ] 20 minutes available
- [ ] PostgreSQL connection possible

**Execute when ready**: Follow steps 1-10 above
