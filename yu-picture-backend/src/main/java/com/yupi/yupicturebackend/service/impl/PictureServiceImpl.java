package com.yupi.yupicturebackend.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.ObjectUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yupi.yupicturebackend.api.ai.AiPictureIndexClient;
import com.yupi.yupicturebackend.api.aliyunai.AliYunAiApi;
import com.yupi.yupicturebackend.api.aliyunai.model.CreateOutPaintingTaskRequest;
import com.yupi.yupicturebackend.api.aliyunai.model.CreateOutPaintingTaskResponse;
import com.yupi.yupicturebackend.model.enums.PictureReviewStatusEnum;
import com.yupi.yupicturebackend.exception.BusinessException;
import com.yupi.yupicturebackend.exception.ErrorCode;
import com.yupi.yupicturebackend.exception.ThrowUtils;
import com.yupi.yupicturebackend.manager.CosManager;
import com.yupi.yupicturebackend.manager.upload.FilePictureUpload;
import com.yupi.yupicturebackend.manager.upload.PictureUploadTemplate;
import com.yupi.yupicturebackend.manager.upload.UrlPictureUpload;
import com.yupi.yupicturebackend.model.dto.file.UploadPictureResult;
import com.yupi.yupicturebackend.model.dto.picture.*;
import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.Space;
import com.yupi.yupicturebackend.model.entity.User;
import com.yupi.yupicturebackend.model.vo.PictureVO;
import com.yupi.yupicturebackend.model.vo.UserVO;
import com.yupi.yupicturebackend.service.PictureService;
import com.yupi.yupicturebackend.mapper.PictureMapper;
import com.yupi.yupicturebackend.service.SpaceService;
import com.yupi.yupicturebackend.service.UserService;
import com.yupi.yupicturebackend.utils.ColorSimilarUtils;
import lombok.extern.slf4j.Slf4j;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.beans.BeanUtils;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import java.awt.*;
import java.io.IOException;
import java.util.*;
import java.util.List;
import java.util.stream.Collectors;

import static com.yupi.yupicturebackend.exception.ThrowUtils.throwIf;

/**
 * @author cass.
 * @description 针对表【picture(图片)】的数据库操作Service实现
 * @createDate 2026-01-31 15:15:34
 */
@Service
@Slf4j
public class PictureServiceImpl extends ServiceImpl<PictureMapper, Picture>
        implements PictureService {
    //    @Resource
//    private FileManager fileManager;
    @Resource
    private FilePictureUpload filePictureUpload;
    @Resource
    private UrlPictureUpload urlPictureUpload;
    @Resource
    private UserService userService;
    @Resource
    private CosManager cosManager;
    @Resource
    private SpaceService spaceService;
    @Resource
    private TransactionTemplate transactionTemplate;
    @Resource
    private AliYunAiApi aliYunAiApi;
    @Resource
    private AiPictureIndexClient aiPictureIndexClient;

    @Override
    public PictureVO uploadPicture(Object inputSource, PictureUploadRequest pictureUploadRequest, User loginUser) {
        //校验参数
        ThrowUtils.throwIf(loginUser == null, ErrorCode.NOT_LOGIN_ERROR);
        //校验空间是否存在
        Long spaceId = pictureUploadRequest.getSpaceId();
        if (spaceId != null) {
            Space space = spaceService.getById(spaceId);
            throwIf(space == null, ErrorCode.PARAMS_ERROR, "该空间不存在");
            //校验是否为本人
            throwIf(!space.getUserId().equals(loginUser.getId()), ErrorCode.NO_AUTH_ERROR, "没有空间权限");
            throwIf(space.getMaxSize() <= space.getTotalSize(), ErrorCode.FORBIDDEN_ERROR, "超出空间余额");
            throwIf(space.getMaxCount() <= space.getTotalCount(), ErrorCode.FORBIDDEN_ERROR, "超出空间余额");
        }
        //校验更改空间是否有权限
        //判断是新增还是删除
        Long picId = null;
        ThrowUtils.throwIf(pictureUploadRequest == null, ErrorCode.PARAMS_ERROR);
        picId = pictureUploadRequest.getId();
        Picture oldPicture = null;
        if (picId != null) {
            oldPicture = getById(picId);
            ThrowUtils.throwIf(oldPicture == null, ErrorCode.NOT_FOUND_ERROR, "图片不存在");
            //仅本人或者管理员可以更新图片
            throwIf(!userService.isAdmin(loginUser)
                    && !loginUser.getId().equals(oldPicture.getUserId()), ErrorCode.NO_AUTH_ERROR, "只能修改自己的图片");
            //校验上传spaceId和源图片的spaceId是否一致
            if (spaceId == null) {
                if (oldPicture.getSpaceId() != null) spaceId = oldPicture.getSpaceId();
            } else {
                throwIf(!spaceId.equals(oldPicture.getSpaceId()), ErrorCode.PARAMS_ERROR, "当前空间与原图空间不一致");
            }
            //删除cos中原有的图片文件
            this.clearPictureFile(oldPicture);
        }
        //按照空间划分目录
        //上传图片
        String uploadPicturePrefix = null;
        if (spaceId == null) {
            //公共图库
            uploadPicturePrefix = String.format("/public/%s", loginUser.getId());
        } else {
            uploadPicturePrefix = String.format("/space/%s", spaceId);
        }
        //根据inputSource的类型判断使用哪个上传方法
        PictureUploadTemplate pictureUploadTemplate = filePictureUpload;
        if (inputSource instanceof String) {
            pictureUploadTemplate = urlPictureUpload;
        }
        UploadPictureResult uploadPictureResult = pictureUploadTemplate.uploadPictureResult(inputSource, uploadPicturePrefix);

        //构造要入库的图片信息
        Picture picture = new Picture();
        picture.setUrl(uploadPictureResult.getUrl());
        //保存缩略图地址
        picture.setThumbnailUrl(uploadPictureResult.getThumbnailUrl());
        picture.setName(uploadPictureResult.getPicName());

        if (StrUtil.isNotBlank(pictureUploadRequest.getPicName())) {
            picture.setName(pictureUploadRequest.getPicName());
        }
        if (CollUtil.isNotEmpty(pictureUploadRequest.getTags())) {
            picture.setTags(JSONUtil.toJsonStr(pictureUploadRequest.getTags()));
        }

        picture.setPicSize(uploadPictureResult.getPicSize());
        picture.setPicWidth(uploadPictureResult.getPicWidth());
        picture.setPicHeight(uploadPictureResult.getPicHeight());
        picture.setPicScale(uploadPictureResult.getPicScale());
        picture.setPicFormat(uploadPictureResult.getPicFormat());
        picture.setUserId(loginUser.getId());
        picture.setSpaceId(spaceId);//指定空间id
        picture.setPicColor(uploadPictureResult.getPicColor());//获取图片主色调
        this.fillReviewParams(picture, loginUser);
        //操作数据库 保存记录
        if (picId != null) {
            picture.setId(picId);
            picture.setEditTime(new Date());
        }
        Long finalSpaceId = spaceId;
        Long finalPicId = picId;
        Picture finalOldPic = oldPicture;
        transactionTemplate.execute(status -> {
            boolean result = this.saveOrUpdate(picture);
            throwIf(!result, ErrorCode.OPERATION_ERROR, "上传图片失败，数据库操作失败");
            if (finalSpaceId != null && finalPicId == null) {
                //更改空间余额,新增图片
                boolean update = spaceService.lambdaUpdate().eq(Space::getId, finalSpaceId)
                        .setSql("totalCount = totalCount+1")
                        .setSql("totalSize = totalSize + " + picture.getPicSize()).update();
                throwIf(!update, ErrorCode.OPERATION_ERROR, "额度更新失败");
            } else if (finalSpaceId != null) {
                //更改空间余额,更改图片
                boolean update = spaceService.lambdaUpdate().eq(Space::getId, finalSpaceId)
                        .setSql("totalSize = totalSize + " + (picture.getPicSize() - finalOldPic.getPicSize())).update();
                throwIf(!update, ErrorCode.OPERATION_ERROR, "额度更新失败");
            }
            return true;
        });
        return PictureVO.objToVo(picture);
    }


    @Override
    public QueryWrapper<Picture> getQueryWrapper(PictureQueryRequest pictureQueryRequest) {
        QueryWrapper<Picture> queryWrapper = new QueryWrapper<>();
        if (pictureQueryRequest == null) {
            return queryWrapper;
        }
        // 从对象中取值
        Long id = pictureQueryRequest.getId();
        String name = pictureQueryRequest.getName();
        String introduction = pictureQueryRequest.getIntroduction();
        String category = pictureQueryRequest.getCategory();
        List<String> tags = pictureQueryRequest.getTags();
        Long picSize = pictureQueryRequest.getPicSize();
        Integer picWidth = pictureQueryRequest.getPicWidth();
        Integer picHeight = pictureQueryRequest.getPicHeight();
        Double picScale = pictureQueryRequest.getPicScale();
        String picFormat = pictureQueryRequest.getPicFormat();
        String searchText = pictureQueryRequest.getSearchText();
        Long userId = pictureQueryRequest.getUserId();
        Integer reviewStatus = pictureQueryRequest.getReviewStatus();
        String reviewMessage = pictureQueryRequest.getReviewMessage();
        Long reviewerId = pictureQueryRequest.getReviewerId();
        Long spaceId = pictureQueryRequest.getSpaceId();
        boolean nullSpaceId = pictureQueryRequest.isNullSpaceId();
        String sortField = pictureQueryRequest.getSortField();
        String sortOrder = pictureQueryRequest.getSortOrder();
        Date endEditTime = pictureQueryRequest.getEndEditTime();
        Date startEditTime = pictureQueryRequest.getStartEditTime();

        // 从多字段中搜索
        if (StrUtil.isNotBlank(searchText)) {
            // 需要拼接查询条件
            queryWrapper.and(
                    qw -> qw.like("name", searchText)
                            .or()
                            .like("introduction", searchText)
            );
        }
        queryWrapper.eq(ObjUtil.isNotEmpty(id), "id", id);
        queryWrapper.eq(ObjUtil.isNotEmpty(userId), "userId", userId);
        queryWrapper.like(StrUtil.isNotBlank(name), "name", name);
        queryWrapper.like(StrUtil.isNotBlank(introduction), "introduction", introduction);
        queryWrapper.like(StrUtil.isNotBlank(picFormat), "picFormat", picFormat);
        queryWrapper.like(ObjUtil.isNotEmpty(reviewMessage), "reviewMessage", reviewMessage);
        queryWrapper.eq(StrUtil.isNotBlank(category), "category", category);
        queryWrapper.eq(ObjUtil.isNotEmpty(picWidth), "picWidth", picWidth);
        queryWrapper.eq(ObjUtil.isNotEmpty(picHeight), "picHeight", picHeight);
        queryWrapper.eq(ObjUtil.isNotEmpty(picSize), "picSize", picSize);
        queryWrapper.eq(ObjUtil.isNotEmpty(picScale), "picScale", picScale);
        queryWrapper.eq(ObjUtil.isNotEmpty(reviewerId), "reviewerId", reviewerId);
        queryWrapper.eq(ObjUtil.isNotEmpty(reviewStatus), "reviewStatus", reviewStatus);
        queryWrapper.eq(ObjectUtil.isNotEmpty((spaceId)), "spaceId", spaceId);
//        queryWrapper.eq(nullSpaceId,"spaceId",0);
        queryWrapper.isNull(nullSpaceId, "spaceId");
        queryWrapper.ge(ObjUtil.isNotEmpty(startEditTime), "editTime", startEditTime);
        queryWrapper.lt(ObjUtil.isNotEmpty(endEditTime), "editTime", endEditTime);
        // JSON 数组查询
        if (CollUtil.isNotEmpty(tags)) {
            //sql语句为 tags like '%"tag"%' and like '%"tag"%'
            for (String tag : tags) {
                queryWrapper.like("tags", "\"" + tag + "\"");
            }
        }
        // 排序
        queryWrapper.orderBy(StrUtil.isNotEmpty(sortField), sortOrder.equals("ascend"), sortField);
        return queryWrapper;
    }

    @Override
    public PictureVO getPictureVO(Picture picture, HttpServletRequest request) {
        // 对象转封装类
        PictureVO pictureVO = PictureVO.objToVo(picture);
        // 关联查询用户信息
        Long userId = picture.getUserId();
        if (userId != null && userId > 0) {
            User user = userService.getById(userId);
            UserVO userVO = userService.getUserVO(user);
            pictureVO.setUser(userVO);
        }
        return pictureVO;
    }


    /**
     * 分页获取图片封装
     */
    @Override
    public Page<PictureVO> getPictureVOPage(Page<Picture> picturePage, HttpServletRequest request) {
        List<Picture> pictureList = picturePage.getRecords();
        Page<PictureVO> pictureVOPage = new Page<>(picturePage.getCurrent(), picturePage.getSize(), picturePage.getTotal());
        if (CollUtil.isEmpty(pictureList)) {
            return pictureVOPage;
        }
        // 对象列表 => 封装对象列表
        List<PictureVO> pictureVOList = pictureList.stream().map(PictureVO::objToVo).collect(Collectors.toList());
        // 1. 关联查询用户信息
        //对用户id去重
        Set<Long> userIdSet = pictureList.stream().map(Picture::getUserId).collect(Collectors.toSet());
        Map<Long, List<User>> userIdUserListMap = userService.listByIds(userIdSet).stream()
                .collect(Collectors.groupingBy(User::getId));
        // 2. 填充信息
        pictureVOList.forEach(pictureVO -> {
            Long userId = pictureVO.getUserId();
            User user = null;
            if (userIdUserListMap.containsKey(userId)) {
                user = userIdUserListMap.get(userId).get(0);
            }
            pictureVO.setUser(userService.getUserVO(user));
        });
        pictureVOPage.setRecords(pictureVOList);
        return pictureVOPage;
    }

    @Override
    public void validPicture(Picture picture) {
        ThrowUtils.throwIf(picture == null, ErrorCode.PARAMS_ERROR);
        // 从对象中取值
        Long id = picture.getId();
        String url = picture.getUrl();
        String introduction = picture.getIntroduction();
        // 修改数据时，id 不能为空，有参数则校验
        ThrowUtils.throwIf(ObjUtil.isNull(id), ErrorCode.PARAMS_ERROR, "id 不能为空");
        if (StrUtil.isNotBlank(url)) {
            ThrowUtils.throwIf(url.length() > 1024, ErrorCode.PARAMS_ERROR, "url 过长");
        }
        if (StrUtil.isNotBlank(introduction)) {
            ThrowUtils.throwIf(introduction.length() > 800, ErrorCode.PARAMS_ERROR, "简介过长");
        }
    }

    @Override
    public void doPictureReview(PictureReviewRequest pictureReviewRequest, User loginUser) {
        //判断图片 校验参数
        ThrowUtils.throwIf(pictureReviewRequest == null, ErrorCode.PARAMS_ERROR);
        Long id = pictureReviewRequest.getId();
        Integer reviewStatus = pictureReviewRequest.getReviewStatus();
        PictureReviewStatusEnum reviewEnum = PictureReviewStatusEnum.getEnumByValue(reviewStatus);
        ThrowUtils.throwIf(id == null || reviewEnum == null ||
                PictureReviewStatusEnum.REVIEWING == reviewEnum, ErrorCode.PARAMS_ERROR);

        Picture oldPicture = getById(id);
        ThrowUtils.throwIf(oldPicture == null, ErrorCode.NOT_FOUND_ERROR);
        //校验审核状态
        ThrowUtils.throwIf(oldPicture.getReviewStatus().equals(reviewStatus), ErrorCode.PARAMS_ERROR, "请勿重复审核");
        //数据库操作
        Picture picture = new Picture();
        BeanUtil.copyProperties(pictureReviewRequest, picture);
        picture.setReviewerId(loginUser.getId());
        //picture.setReviewMessage(reviewMessage);
        picture.setReviewTime(new Date());
        //picture.setReviewStatus(reviewStatus);
        boolean result = updateById(picture);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "更新图片审核状态失败");
    }


    @Override
    public void fillReviewParams(Picture picture, User loginUser) {
        throwIf(picture == null, ErrorCode.PARAMS_ERROR);
        if (userService.isAdmin(loginUser)) {
            picture.setReviewStatus(PictureReviewStatusEnum.PASS.getValue());
            picture.setReviewMessage("管理员自动过审");
            picture.setReviewerId(loginUser.getId());
            picture.setReviewTime(new Date());
        } else {
            picture.setReviewStatus(PictureReviewStatusEnum.REVIEWING.getValue());
        }
    }

    @Override
    public Integer uploadPictureByBatch(PictureUploadBatchRequest pictureUploadBatchRequest,
                                        User loginUser) {
        //校验参数
        String searchText = pictureUploadBatchRequest.getSearchText();
        Integer count = pictureUploadBatchRequest.getCount();
        String namePrefix = pictureUploadBatchRequest.getNamePrefix();
        List<String> tags = pictureUploadBatchRequest.getTags();
        if (StrUtil.isBlank(namePrefix)) {
            namePrefix = searchText;
        }
        throwIf(count > 30, ErrorCode.PARAMS_ERROR, "最多可传30条");
        //抓取内容
        String fetchUrl = String.format("https://cn.bing.com/images/async?q=%s&mmasync=1", searchText);
        Document document;
        try {
            document = Jsoup.connect(fetchUrl).get();
        } catch (IOException e) {
            log.error("获取页面失败", e);
            throw new BusinessException(ErrorCode.OPERATION_ERROR);
        }
        //解析内容
        Element div = document.getElementsByClass("dgControl").first();
        throwIf(ObjectUtil.isEmpty(div), ErrorCode.OPERATION_ERROR, "获取元素失败");
        Elements imgElementList = div.select("img.mimg");
        int uploadCount = 0;
        for (Element imgElement : imgElementList) {
            String fileUrl = imgElement.attr("src");
            if (StrUtil.isBlank(fileUrl)) {
                log.info("当前链接为空，已跳过：{}", fileUrl);
                continue;
            }
            //处理图片的地址，防止转义或者对象存储冲突的问题
            int questionIndex = fileUrl.indexOf("?");
            if (questionIndex > -1) {
                fileUrl = fileUrl.substring(0, questionIndex);
            }
            log.info("文件地址：{}", fileUrl);
            PictureUploadRequest pictureUploadRequest = new PictureUploadRequest();
            pictureUploadRequest.setFileUrl(fileUrl);
            pictureUploadRequest.setPicName(namePrefix + (uploadCount + 1));
            pictureUploadRequest.setTags(tags);
            PictureVO pictureVO;
            try {
                pictureVO = this.uploadPicture(fileUrl, pictureUploadRequest, loginUser);
                log.info("已上传的图片 ：id = {}", pictureVO.getId());
                uploadCount++;
            } catch (Exception e) {
                log.error("上传文件失败", e);
            }
            if (uploadCount >= count) break;
        }
        return uploadCount;
    }

    /**
     * 删除图片文件
     *
     * @param oldPicture
     */
    @Override
    @Async
    public void clearPictureFile(Picture oldPicture) {
        //判断图片是否被多条记录使用
        String url = oldPicture.getUrl();
        Long count = lambdaQuery().eq(Picture::getUrl, url).count();
        //如果不只一条数据用到了该图片，则不清理
        if (count > 1) return;
        //删除原始webp
        cosManager.deleteObject(url);
        //删除缩略图
        if (StrUtil.isBlank(oldPicture.getThumbnailUrl())) return;
        cosManager.deleteObject(oldPicture.getThumbnailUrl());
    }

    @Override
    public void checkPictureAuth(Picture picture, User loginUser) {
        Long spaceId = picture.getSpaceId();
        if (spaceId == null) {
            throwIf(!userService.isAdmin(loginUser) && !loginUser.getId().equals(picture.getUserId()), ErrorCode.NO_AUTH_ERROR);
        } else {
            throwIf(!loginUser.getId().equals(picture.getUserId()), ErrorCode.NO_AUTH_ERROR);
        }
    }

    @Override
    public void deletePicture(Long pictureId, User loginUser) {
        Picture picture = this.getById(pictureId);
        //判断图片是否存在
        ThrowUtils.throwIf(picture == null, ErrorCode.PARAMS_ERROR, "图片不存在");
        //校验权限 已经改为注解鉴权
        //this.checkPictureAuth(picture, loginUser);
        //更新空间容量
        Long finalSpaceId = picture.getSpaceId();
        transactionTemplate.execute(status -> {
            //删除数据库中的数据
            boolean deleteResult = this.removeById(picture.getId());
            ThrowUtils.throwIf(!deleteResult, ErrorCode.OPERATION_ERROR, "数据异常，删除图片失败");
            if (finalSpaceId != null) {
                //更改空间余额,新增图片
                boolean update = spaceService.lambdaUpdate().eq(Space::getId, finalSpaceId)
                        .setSql("totalCount = totalCount-1")
                        .setSql("totalSize = totalSize - " + picture.getPicSize()).update();
                throwIf(!update, ErrorCode.OPERATION_ERROR, "额度更新失败");
            }
            return true;
        });
        aiPictureIndexClient.removePictureIndex(picture.getId(), finalSpaceId);
        //删除cos中的文件
        this.clearPictureFile(picture);
    }

    @Override
    public void editPicture(PictureEditRequest pictureEditRequest, User loginUser) {
        // 判断是否存在
        long id = pictureEditRequest.getId();
        Picture oldPicture = this.getById(id);
        ThrowUtils.throwIf(oldPicture == null, ErrorCode.NOT_FOUND_ERROR);
        //校验空间权限 已改为注解鉴权
        //this.checkPictureAuth(oldPicture, loginUser);
        // 在此处将实体类和 DTO 进行转换
        Picture picture = new Picture();
        BeanUtils.copyProperties(pictureEditRequest, picture);
        //补充审核参数
        this.fillReviewParams(picture, loginUser);
        // 注意将 list 转为 string
        picture.setTags(JSONUtil.toJsonStr(pictureEditRequest.getTags()));
        // 数据校验
        this.validPicture(picture);
        // 设置编辑时间
        picture.setEditTime(new Date());
        // 操作数据库
        boolean result = this.updateById(picture);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR);
    }

    @Override
    public List<PictureVO> searchPictureByColor(Long spaceId, String pictureColor, User loginUser) {
        //校验参数
        throwIf(spaceId == null || StrUtil.isBlank(pictureColor), ErrorCode.PARAMS_ERROR);
        Space space = spaceService.getById(spaceId);
        throwIf(space == null, ErrorCode.PARAMS_ERROR, "空间不存在");
        //校验权限
        throwIf(!space.getUserId().equals(loginUser.getId()), ErrorCode.NO_AUTH_ERROR);
        //查询该空间下的所有图片
        List<Picture> pictures = lambdaQuery()
                .eq(Picture::getSpaceId, spaceId)
                .isNotNull(Picture::getPicColor)
                .list();
        if (CollUtil.isEmpty(pictures)) {
            return new ArrayList<>();
        }
        //转换传入的颜色主色调
        Color targetColor = Color.decode(pictureColor);
        //计算相似度并排序
        List<PictureVO> collect = pictures.stream()
                .sorted(Comparator.comparingDouble(picture -> {
                    String hexColor = picture.getPicColor();
                    if (StrUtil.isBlank(hexColor)) {
                        return Double.MAX_VALUE;
                    }
                    Color picColor = Color.decode(hexColor);
                    return -ColorSimilarUtils.calculateSimilarity(picColor, targetColor);
                }))
                .limit(12)//取前十二条
                .map(PictureVO::objToVo).collect(Collectors.toList());
        if (CollUtil.isEmpty(collect)) {
            return new ArrayList<>();
        }
        return collect;
    }

    @Override
    public void editPictureByBatch(PictureEditByBatchRequest pictureEditByBatchRequest, User loginUser) {
        //获取和校验参数
        List<Long> pictureIdList = pictureEditByBatchRequest.getPictureIdList();
        Long spaceId = pictureEditByBatchRequest.getSpaceId();
        String category = pictureEditByBatchRequest.getCategory();
        List<String> tags = pictureEditByBatchRequest.getTags();
        throwIf(CollUtil.isEmpty(pictureIdList) || spaceId == null, ErrorCode.PARAMS_ERROR);
        throwIf(loginUser == null, ErrorCode.NO_AUTH_ERROR);
        //校验空间权限
        Space space = spaceService.getById(spaceId);
        throwIf(space == null, ErrorCode.PARAMS_ERROR, "空间不存在");
        throwIf(!space.getUserId().equals(loginUser.getId()), ErrorCode.NO_AUTH_ERROR);
        //查询图片是否存在（仅选择需要的字段）
        List<Picture> oldPictures = lambdaQuery()
                .select(Picture::getId, Picture::getSpaceId)
                .eq(Picture::getSpaceId, spaceId)
                .in(Picture::getId, pictureIdList)
                .list();
        if (CollUtil.isEmpty(oldPictures)) return;
        //更新图片的分类和标签
        oldPictures.forEach(picture -> {
            if (StrUtil.isNotBlank(category)) {
                picture.setCategory(category);
            }
            if (CollUtil.isNotEmpty(tags)) {
                picture.setTags(JSONUtil.toJsonStr(tags));
            }
        });
        //批量重命名
        String nameRule = pictureEditByBatchRequest.getNameRule();
        if (StrUtil.isNotBlank(nameRule)) {
            fillPictureWithNameRule(oldPictures, nameRule);
        }

        //操作数据库
        boolean result = this.updateBatchById(oldPictures);
        throwIf(!result, ErrorCode.OPERATION_ERROR, "批量编辑失败");
    }

    @Override
    public CreateOutPaintingTaskResponse createPictureOutPaintingTask(CreatePictureOutPaintingTaskRequest createPictureOutPaintingTaskRequest, User loginUser) {
        //获取图片信息
        Long pictureId = createPictureOutPaintingTaskRequest.getPictureId();
        Picture picture = this.getById(pictureId);
        throwIf(picture == null, ErrorCode.PARAMS_ERROR, "图片不存在");
        //校验权限 已改为注解鉴权
        //checkPictureAuth(picture, loginUser);
        //创建扩图任务
        CreateOutPaintingTaskRequest createOutPaintingTaskRequest = new CreateOutPaintingTaskRequest();
        CreateOutPaintingTaskRequest.Input input = new CreateOutPaintingTaskRequest.Input();
        input.setImageUrl(picture.getUrl());
        createOutPaintingTaskRequest.setInput(input);
        createOutPaintingTaskRequest.setParameters(createPictureOutPaintingTaskRequest.getParameters());

        return aliYunAiApi.createOutPaintingTaskResponse(createOutPaintingTaskRequest);
    }

    /**
     * namerule 格式：图片{序号}
     *
     * @param oldPictures
     * @param nameRule
     */
    private void fillPictureWithNameRule(List<Picture> oldPictures, String nameRule) {
        long count = 1;
        try {
            for (Picture picture : oldPictures) {
                String picName = nameRule.replaceAll("\\{序号}", String.valueOf(count++));
                picture.setName(picName);
            }
        } catch (Exception e) {
            log.error("名称解析错误", e);
            throw new BusinessException(ErrorCode.OPERATION_ERROR, "名称解析错误");
        }
    }
}



