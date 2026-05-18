package com.yupi.yupicturebackend.service.impl;

import cn.hutool.core.util.NumberUtil;
import cn.hutool.core.util.ObjectUtil;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yupi.yupicturebackend.exception.BusinessException;
import com.yupi.yupicturebackend.exception.ErrorCode;
import com.yupi.yupicturebackend.mapper.SpaceMapper;
import com.yupi.yupicturebackend.model.dto.space.analyze.*;
import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.Space;
import com.yupi.yupicturebackend.model.entity.User;
import com.yupi.yupicturebackend.model.vo.space.analyze.*;
import com.yupi.yupicturebackend.service.PictureService;
import com.yupi.yupicturebackend.service.SpaceAnalyzeService;
import com.yupi.yupicturebackend.service.SpaceService;
import com.yupi.yupicturebackend.service.UserService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;

import java.math.BigDecimal;
import java.util.*;
import java.util.stream.Collectors;

import static com.yupi.yupicturebackend.exception.ThrowUtils.throwIf;


@Service
@Slf4j
public class SpaceAnalyzeServiceImpl extends ServiceImpl<SpaceMapper, Space>
        implements SpaceAnalyzeService {
    @Resource
    private UserService userService;
    @Resource
    private SpaceService spaceService;
    @Resource
    private PictureService pictureService;

    @Override
    public SpaceUsageAnalyzeResponse getSpaceUsageAnalyze(SpaceUsageAnalyzeRequest spaceUsageAnalyzeRequest, User loginUser) {
        throwIf(spaceUsageAnalyzeRequest == null, ErrorCode.PARAMS_ERROR);
        //校验权限
        checkSpaceAnalyzeAuth(spaceUsageAnalyzeRequest, loginUser);
        //全空间或公共图库 需要从picture表查询
        //特定空间直接从space表查询
        if (spaceUsageAnalyzeRequest.isQueryAll() || spaceUsageAnalyzeRequest.isQueryPublic()) {
            //统计公共图库的使用
            QueryWrapper<Picture> queryWrapper = new QueryWrapper<>();
            fillAnalyzeQueryWrapper(queryWrapper, spaceUsageAnalyzeRequest);
            queryWrapper.select("picSize");
            List<Object> pictureObjList = pictureService.getBaseMapper().selectObjs(queryWrapper);
            long usedSize = pictureObjList.stream().mapToLong(obj -> (Long) obj).sum();
            long usedCount = pictureObjList.size();
            //封装返回结果
            SpaceUsageAnalyzeResponse spaceUsageAnalyzeResponse = new SpaceUsageAnalyzeResponse();
            spaceUsageAnalyzeResponse.setUsedSize(usedSize);
            spaceUsageAnalyzeResponse.setUsedCount(usedCount);
            return spaceUsageAnalyzeResponse;
        } else {
            Long spaceId = spaceUsageAnalyzeRequest.getSpaceId();
            throwIf(spaceId == null, ErrorCode.PARAMS_ERROR);
            Space space = spaceService.getById(spaceId);
            throwIf(space == null, ErrorCode.PARAMS_ERROR, "空间不存在");
            Long totalCount = space.getTotalCount();
            Long totalSize = space.getTotalSize();
            Long maxCount = space.getMaxCount();
            Long maxSize = space.getMaxSize();
            SpaceUsageAnalyzeResponse spaceUsageAnalyzeResponse = new SpaceUsageAnalyzeResponse();
            spaceUsageAnalyzeResponse.setUsedSize(totalSize);
            spaceUsageAnalyzeResponse.setMaxSize(maxSize);
            BigDecimal size = NumberUtil.round(totalSize * 100.0 / maxSize, 2);
            spaceUsageAnalyzeResponse.setSizeUsageRatio(size.doubleValue());
            spaceUsageAnalyzeResponse.setUsedCount(totalCount);
            spaceUsageAnalyzeResponse.setMaxCount(maxCount);
            BigDecimal count = NumberUtil.round(totalCount * 100.0 / maxCount, 2);
            spaceUsageAnalyzeResponse.setCountUsageRatio(count.doubleValue());
            return spaceUsageAnalyzeResponse;
        }
    }

    @Override
    public List<SpaceCategoryAnalyzeResponse> getSpaceCategoryAnalyze(SpaceCategoryAnalyzeRequest spaceCategoryAnalyzeRequest, User loginUser) {
        throwIf(spaceCategoryAnalyzeRequest == null, ErrorCode.PARAMS_ERROR);
        //校验权限
        checkSpaceAnalyzeAuth(spaceCategoryAnalyzeRequest, loginUser);
        //构造查询条件
        QueryWrapper<Picture> queryWrapper = new QueryWrapper<>();
        fillAnalyzeQueryWrapper(queryWrapper, spaceCategoryAnalyzeRequest);
        //分组查询
        queryWrapper.select("category", "count(*) as count", "sum(picSize) as totalSize")
                .groupBy("category");
        //查询并转换结果
        return pictureService.getBaseMapper().selectMaps(queryWrapper).stream().map(result -> {
            String category = (String) result.get("category");
            Long count = (Long) result.get("count");
            Long totalSize = ((BigDecimal) result.get("totalSize")).longValue();
            return new SpaceCategoryAnalyzeResponse(category, count, totalSize);
        }).collect(Collectors.toList());
    }

    @Override
    public List<SpaceTagAnalyzeResponse> getSpaceTagAnalyze(SpaceTagAnalyzeRequest spaceTagAnalyzeRequest, User loginUser) {
        throwIf(spaceTagAnalyzeRequest == null, ErrorCode.PARAMS_ERROR);
        checkSpaceAnalyzeAuth(spaceTagAnalyzeRequest, loginUser);
        //构建查询条件
        QueryWrapper<Picture> queryWrapper = new QueryWrapper<>();
        fillAnalyzeQueryWrapper(queryWrapper, spaceTagAnalyzeRequest);
        //查询所有标签
        queryWrapper.select("tags");
        List<String> tagsJsonList = pictureService.getBaseMapper().selectObjs(queryWrapper).stream()
                .filter(ObjectUtil::isNotNull).map(Object::toString).collect(Collectors.toList());
        //拆分标签并统计
        Map<String, Long> tagCounts = tagsJsonList.stream().flatMap(tagsJson -> JSONUtil.toList(tagsJson, String.class).stream())
                .collect(Collectors.groupingBy(tag -> tag, Collectors.counting()));
        //转换为响应对象，按照次数大小排序
        return tagCounts.entrySet().stream()
                .sorted((e1, e2) -> Long.compare(e2.getValue(), e1.getValue()))//降序
                .map(entry -> new SpaceTagAnalyzeResponse(entry.getKey(), entry.getValue())).collect(Collectors.toList());
    }

    @Override
    public List<SpaceSizeAnalyzeResponse> getSpaceSizeAnalyze(SpaceSizeAnalyzeRequest spaceSizeAnalyzeRequest, User loginUser) {
        throwIf(spaceSizeAnalyzeRequest == null, ErrorCode.PARAMS_ERROR);
        checkSpaceAnalyzeAuth(spaceSizeAnalyzeRequest, loginUser);
        //构建查询条件
        QueryWrapper<Picture> queryWrapper = new QueryWrapper<>();
        fillAnalyzeQueryWrapper(queryWrapper, spaceSizeAnalyzeRequest);
        //查询图片大小
        queryWrapper.select("picSize");
        List<Long> picSizeList = pictureService.getBaseMapper().selectObjs(queryWrapper).stream()
                .map(size -> (Long) size).collect(Collectors.toList());
        //定义分段范围
        Map<String, Long> sizeRangeMap = new LinkedHashMap<>();
        sizeRangeMap.put("<100KB", picSizeList.stream().filter(size -> size > 100 * 1024).count());
        sizeRangeMap.put("100KB-500KB", picSizeList.stream().filter(size -> size >= 100 * 1024 && size < 500 * 1024).count());
        sizeRangeMap.put("500KB-1MB", picSizeList.stream().filter(size -> size >= 500 * 1024 && size < 1024 * 1024).count());
        sizeRangeMap.put(">1MB", picSizeList.stream().filter(size -> size >= 1024 * 1024).count());
        //转换响应对象
        return sizeRangeMap.entrySet()
                .stream()
                .map(entry -> new SpaceSizeAnalyzeResponse(entry.getKey(), entry.getValue()))
                .collect(Collectors.toList());
    }

    @Override
    public List<SpaceUserAnalyzeResponse> getUserUploadAnalyze(SpaceUserAnalyzeRequest spaceUserAnalyzeRequest, User loginUser) {
        throwIf(spaceUserAnalyzeRequest == null, ErrorCode.PARAMS_ERROR);
        checkSpaceAnalyzeAuth(spaceUserAnalyzeRequest, loginUser);
        //构建查询条件
        QueryWrapper<Picture> queryWrapper = new QueryWrapper<>();
        //补充用户id查询
        Long userId = spaceUserAnalyzeRequest.getUserId();
        queryWrapper.eq(userId != null, "userId", userId);
        String timeDimension = spaceUserAnalyzeRequest.getTimeDimension();
        switch (timeDimension) {
            case "day":
                queryWrapper.select("DATE_FORMAT(createTime,'%Y-%m-%d') as period", "count(*) as count");
                break;
            case "week":
                queryWrapper.select("YEARWEEK(createTime) as period", "count(*) as count");
                break;
            case "month":
                queryWrapper.select("DATE_FORMAT(createTime,'%Y-%m') as period", "count(*) as count");
                break;
            default:
                throw new BusinessException(ErrorCode.PARAMS_ERROR, "不支持此时间维度");
        }
        //分组排序
        queryWrapper.groupBy("period").orderByAsc("period");
        List<Map<String, Object>> queryResult = pictureService.getBaseMapper().selectMaps(queryWrapper);
        return queryResult.stream().map(result -> {
            SpaceUserAnalyzeResponse spaceUserAnalyzeResponse = new SpaceUserAnalyzeResponse();
            spaceUserAnalyzeResponse.setPeriod((String) result.get("period"));
            spaceUserAnalyzeResponse.setCount((Long) result.get("count"));
            return spaceUserAnalyzeResponse;
        }).collect(Collectors.toList());

    }

    @Override
    public List<Space> getSpaceRankAnalyze(SpaceRankAnalyzeRequest spaceRankAnalyzeRequest, User loginUser) {
        throwIf(spaceRankAnalyzeRequest == null, ErrorCode.PARAMS_ERROR);
        //仅管理员
        throwIf(!userService.isAdmin(loginUser), ErrorCode.NO_AUTH_ERROR);
        //构建查询条件
        QueryWrapper<Space> queryWrapper = new QueryWrapper<>();
        queryWrapper.select("id", "spaceName", "userId", "totalSize")
                .orderByDesc("totalSize")
                .last("limit " + spaceRankAnalyzeRequest.getTopN());//取前n个
        return spaceService.list(queryWrapper);
    }

    /**
     * 校验空间分析权限
     *
     * @param spaceAnalyzeRequest
     * @param loginUser
     */
    private void checkSpaceAnalyzeAuth(SpaceAnalyzeRequest spaceAnalyzeRequest, User loginUser) {
        Long spaceId = spaceAnalyzeRequest.getSpaceId();
        boolean queryPublic = spaceAnalyzeRequest.isQueryPublic();
        boolean queryAll = spaceAnalyzeRequest.isQueryAll();
        if (queryPublic || queryAll) {
            throwIf(!userService.isAdmin(loginUser), ErrorCode.NO_AUTH_ERROR);
        } else {
            throwIf(spaceId == null, ErrorCode.PARAMS_ERROR);
            Space space = spaceService.getById(spaceId);
            throwIf(space == null, ErrorCode.PARAMS_ERROR);
            Long userId = space.getUserId();
            spaceService.checkSpaceAuth(loginUser, space);
        }
    }

    /**
     * 根据请求对象封装查询条件
     *
     * @param queryWrapper
     * @param spaceAnalyzeRequest
     */
    private void fillAnalyzeQueryWrapper(QueryWrapper<Picture> queryWrapper, SpaceAnalyzeRequest spaceAnalyzeRequest) {
        Long spaceId = spaceAnalyzeRequest.getSpaceId();
        boolean queryPublic = spaceAnalyzeRequest.isQueryPublic();
        boolean queryAll = spaceAnalyzeRequest.isQueryAll();
        if (queryPublic) {
            queryWrapper.isNull("spaceId");
            return;
        } else if (spaceId != null) {
            queryWrapper.eq("spaceId", spaceId);
            return;
        } else if (queryAll) {
            return;
        }
        throw new BusinessException(ErrorCode.PARAMS_ERROR, "为指定查询范围");
    }

}
